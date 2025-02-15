# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - PaaS 平台 (BlueKing - PaaS System) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except
in compliance with the License. You may obtain a copy of the License at

    http://opensource.org/licenses/MIT

Unless required by applicable law or agreed to in writing, software distributed under
the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language governing permissions and
limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import logging
import time
from typing import Optional, Type

from django.db import IntegrityError

from paas_wl.cnative.specs import svc_disc
from paas_wl.cnative.specs.constants import DeployStatus
from paas_wl.cnative.specs.entities import BkAppManifestProcessor
from paas_wl.cnative.specs.models import AppModelDeploy, AppModelRevision
from paas_wl.cnative.specs.mounts import VolumeSourceManager
from paas_wl.cnative.specs.resource import deploy as apply_bkapp_to_k8s
from paas_wl.monitoring.bklog.shim import make_bk_log_controller
from paas_wl.platform.applications.models import Build
from paas_wl.resources.base.kres import KNamespace
from paas_wl.resources.utils.basic import get_client_by_app
from paasng.engine.constants import JobStatus
from paasng.engine.deploy.bg_wait.wait_bkapp import AppModelDeployStatusPoller, DeployStatusHandler
from paasng.engine.exceptions import StepNotInPresetListError
from paasng.engine.models.phases import DeployPhaseTypes
from paasng.engine.workflow import DeployStep
from paasng.platform.applications.models import ModuleEnvironment

logger = logging.getLogger(__name__)

# Try to load the access control module
ApplicationAccessControlSwitch: Optional[Type]
try:
    from paasng.security.access_control.models import ApplicationAccessControlSwitch
except ImportError:
    logger.info('access control only supported in te edition, skip import')
    ApplicationAccessControlSwitch = None


class BkAppReleaseMgr(DeployStep):
    """BkApp(CRD) Release Step, will schedule the Deployment/Ingress and so on by k8s operator.
    The k8s operator is deployed at app cluster"""

    PHASE_TYPE = DeployPhaseTypes.RELEASE

    def start(self):
        build = Build.objects.get(pk=self.deployment.build_id)
        # 优先使用本次部署指定的 revision, 如果未指定, 则使用与构建产物关联 revision(由(源码提供的 bkapp.yaml 创建)
        revision = AppModelRevision.objects.get(pk=self.deployment.bkapp_revision_id or build.bkapp_revision_id)
        with self.procedure('部署应用'):
            bkapp_release_id = release_by_k8s_operator(
                self.module_environment,
                revision,
                operator=self.deployment.operator,
                deployment_id=self.deployment.id,
                build=build,
            )

        # 这里只是轮询开始，具体状态更新需要放到轮询组件中完成
        self.state_mgr.update(bkapp_release_id=bkapp_release_id)
        try:
            step_obj = self.phase.get_step_by_name(name="检测部署结果")
            step_obj.mark_and_write_to_stream(
                self.stream, JobStatus.PENDING, extra_info={"bkapp_release_id": bkapp_release_id}
            )
        except StepNotInPresetListError:
            logger.debug("Step not found or duplicated, name: %s", "检测部署结果")


def release_by_k8s_operator(
    env: ModuleEnvironment,
    revision: AppModelRevision,
    operator: str,
    build: Optional[Build] = None,
    deployment_id: Optional[str] = None,
) -> str:
    """Create a new release for given environment(which will be handled by k8s operator).
    this action will start an async waiting procedure which waits for the release to be finished.

    :param env: The environment to create the release for.
    :param revision: The revision to be released.
    :param operator: current operator's user_id
    :param deployment_id: the deployment id of the release

    :raises: ValueError when image credential_refs is invalid  TODO: 抛更具体的异常
    :raises: UnprocessibleEntityError when k8s can not process this manifest
    :raises: other unknown exceptions...
    """
    application = env.application
    module = env.module

    # TODO: read name from request data or generate by model resource payload
    # Add current timestamp in name to avoid conflicts
    default_name = f'{application.code}-{revision.pk}-{int(time.time())}'

    try:
        app_model_deploy = AppModelDeploy.objects.create(
            application_id=application.id,
            module_id=module.id,
            environment_name=env.environment,
            name=default_name,
            revision=revision,
            status=DeployStatus.PENDING.value,
            operator=operator,
        )
    except IntegrityError:
        logger.warning("Name conflicts when creating new AppModelDeploy object, name: %s.", default_name)
        raise

    try:
        # 下发 k8s 资源前需要确保命名空间存在
        ensure_namespace(env)

        # Apply the ConfigMap resource related with service discovery
        #
        # NOTE: This action might break running pods that get svc-discovery data by
        # mounting the configmap as file, because some data might be removed in the
        # latest version. We should ask the application developer to handle this properly.
        svc_disc.apply_configmap(env, app_model_deploy.bk_app_resource)

        # 下发待挂载的 volume source
        VolumeSourceManager(env).deploy()

        if ApplicationAccessControlSwitch is not None:
            acl_enabled = ApplicationAccessControlSwitch.objects.is_enabled(application)
        else:
            acl_enabled = False

        deployed_manifest = apply_bkapp_to_k8s(
            env, BkAppManifestProcessor(app_model_deploy).build_manifest(build=build, acl_enabled=acl_enabled)
        )

        # 下发日志采集配置
        ensure_bk_log_if_need(env)
    except Exception:
        app_model_deploy.status = DeployStatus.ERROR
        app_model_deploy.save(update_fields=["status", "updated"])
        raise

    revision.deployed_value = deployed_manifest
    revision.has_deployed = True
    revision.save(update_fields=["deployed_value", "has_deployed", "updated"])

    # TODO: 统计成功 metrics
    # Poll status in background
    AppModelDeployStatusPoller.start(
        {'deploy_id': app_model_deploy.id, 'deployment_id': deployment_id}, DeployStatusHandler
    )
    return str(app_model_deploy.id)


def ensure_namespace(env: ModuleEnvironment, max_wait_seconds: int = 15) -> bool:
    """确保命名空间存在, 如果命名空间不存在, 那么将创建一个 Namespace 和 ServiceAccount

    :param env: ModuleEnvironment
    :param max_wait_seconds: 等待 ServiceAccount 就绪的时间
    :return: whether an namespace was created.
    """
    wl_app = env.wl_app
    with get_client_by_app(wl_app) as client:
        namespace_client = KNamespace(client)
        _, created = namespace_client.get_or_create(name=wl_app.namespace)
        if created:
            namespace_client.wait_for_default_sa(namespace=wl_app.namespace, timeout=max_wait_seconds)
        return created


def ensure_bk_log_if_need(env: ModuleEnvironment):
    """如果集群支持且应用声明了 BkLogConfig, 则尝试下发日志采集配置"""
    try:
        # 下发 BkLogConfig
        make_bk_log_controller(env).create_or_patch()
    except Exception:
        logger.exception("An error occur when creating BkLogConfig")
