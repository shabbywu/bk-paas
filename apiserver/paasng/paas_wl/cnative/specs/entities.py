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
import json
import logging
from typing import Dict, Optional

from paas_wl.cnative.specs import mounts
from paas_wl.cnative.specs.configurations import (
    generate_builtin_configurations,
    generate_user_configurations,
    merge_envvars,
)
from paas_wl.cnative.specs.constants import (
    ACCESS_CONTROL_ANNO_KEY,
    BKAPP_CODE_ANNO_KEY,
    BKAPP_NAME_ANNO_KEY,
    BKAPP_REGION_ANNO_KEY,
    BKPAAS_ADDONS_ANNO_KEY,
    BKPAAS_DEPLOY_ID_ANNO_KEY,
    ENVIRONMENT_ANNO_KEY,
    IMAGE_CREDENTIALS_REF_ANNO_KEY,
    MODULE_NAME_ANNO_KEY,
    PA_SITE_ID_ANNO_KEY,
    USE_CNB_ANNO_KEY,
    WLAPP_NAME_ANNO_KEY,
    ApiVersion,
)
from paas_wl.cnative.specs.models import AppModelDeploy, BkAppResource
from paas_wl.platform.applications.models import Build, WlApp
from paas_wl.platform.applications.models.managers.app_metadata import get_metadata
from paasng.dev_resources.servicehub.manager import mixed_service_mgr
from paasng.platform.applications.models import Application, ModuleEnvironment

logger = logging.getLogger(__name__)


class BkAppManifestProcessor:
    """BkAppManifest 处理器, 功能定位同 AppEntitySerializer"""

    def __init__(self, model_deploy: AppModelDeploy):
        self.env = model_deploy.environment
        self.model_deploy = model_deploy

    def build_manifest(self, build: Optional[Build] = None, acl_enabled: bool = False) -> Dict:
        """inject bkpaas-specific properties to annotations

        :param build: optional, artifact build by platform
            if build.image is not None, will overwrite the image filed in manifest
            if the image is built by CNB runtime, will set `use-cnb` annotation to "true"
        :param acl_enabled: whether the access control module is enabled.
        """
        wl_app = WlApp.objects.get(pk=self.env.engine_app_id)
        manifest = BkAppResource(**self.model_deploy.revision.json_value)

        use_cnb = False
        if build:
            if build.image:
                # 替换镜像信息
                # 对于仅托管镜像类型的云原生应用, build.image 字段为空字符串
                # 对于从源码构建镜像的云原生应用, build.image 字段是构建后的镜像
                self._patch_image(manifest, build.image)
            use_cnb = build.artifact_metadata.get("use_cnb", False)

        # 更新注解，包含应用基本信息，增强服务，访问控制，镜像凭证等
        self._inject_annotations(
            manifest, self.env.application, self.env, wl_app, use_cnb=use_cnb, acl_enabled=acl_enabled
        )

        # 注入用户自定义变量，与 YAML 中定义的进行合并，优先级：页面填写的 > YAML 中已有的
        manifest.spec.configuration.env = merge_envvars(
            manifest.spec.configuration.env, generate_user_configurations(env=self.env)
        )

        # 注入平台内置环境变量
        manifest.spec.configuration.env = merge_envvars(
            manifest.spec.configuration.env, generate_builtin_configurations(env=self.env)
        )

        # 注入挂载信息
        mounts.inject_to_app_resource(self.env, manifest)

        data = manifest.dict()
        # refresh status.conditions
        data["status"] = {"conditions": []}
        return data

    def _patch_image(self, manifest: BkAppResource, image: Optional[str] = None) -> None:
        if manifest.apiVersion == ApiVersion.V1ALPHA2 and manifest.spec.build:
            manifest.spec.build.image = image

        elif manifest.apiVersion == ApiVersion.V1ALPHA1:
            for p in manifest.spec.processes:
                p.image = image

    def _inject_annotations(
        self,
        manifest: BkAppResource,
        application: Application,
        env: ModuleEnvironment,
        wl_app: WlApp,
        use_cnb: bool = False,
        acl_enabled: bool = False,
    ) -> None:
        # inject bkapp deploy info
        manifest.metadata.annotations[BKPAAS_DEPLOY_ID_ANNO_KEY] = str(self.model_deploy.pk)

        # inject bkapp basic info
        manifest.metadata.annotations.update(
            {
                BKAPP_REGION_ANNO_KEY: application.region,
                BKAPP_NAME_ANNO_KEY: application.name,
                BKAPP_CODE_ANNO_KEY: application.code,
                MODULE_NAME_ANNO_KEY: env.module.name,
                ENVIRONMENT_ANNO_KEY: env.environment,
                WLAPP_NAME_ANNO_KEY: wl_app.name,
            }
        )
        # inject image type
        manifest.metadata.annotations.update(
            {
                # cnb 运行时启动 Process 的 entrypoint 是 `process_type`, command 是空列表
                # cnb 运行时执行其他命令需要用 `launcher` 进入 buildpack 上下文
                # See: https://github.com/buildpacks/lifecycle/blob/main/cmd/launcher/cli/launcher.go
                USE_CNB_ANNO_KEY: ("true" if use_cnb else "false"),
            }
        )

        # inject addons services
        manifest.metadata.annotations[BKPAAS_ADDONS_ANNO_KEY] = json.dumps(
            [svc.name for svc in mixed_service_mgr.list_binded(env.module)]
        )

        # inject pa site id when the feature is enabled
        if bkpa_site_id := get_metadata(wl_app).bkpa_site_id:
            manifest.metadata.annotations[PA_SITE_ID_ANNO_KEY] = str(bkpa_site_id)

        # always inject a flag to tell operator that workloads have created the secret
        manifest.metadata.annotations[IMAGE_CREDENTIALS_REF_ANNO_KEY] = "true"

        # inject access control enable info
        if acl_enabled:
            manifest.metadata.annotations[ACCESS_CONTROL_ANNO_KEY] = "true"
