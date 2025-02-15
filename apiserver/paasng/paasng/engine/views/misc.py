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
import datetime
import logging

from bkpaas_auth.models import user_id_encoder
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import gettext as _
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from paas_wl.monitoring.metrics.exceptions import (
    AppInstancesNotFoundError,
    AppMetricNotSupportedError,
    RequestMetricBackendError,
)
from paas_wl.monitoring.metrics.shim import list_app_proc_all_metrics, list_app_proc_metrics
from paas_wl.monitoring.metrics.utils import MetricSmartTimeRange
from paas_wl.platform.system_api.serializers import InstanceMetricsResultSerializer, ResourceMetricsResultSerializer
from paasng.accessories.iam.helpers import fetch_user_roles
from paasng.accessories.iam.permissions.resources.application import AppAction
from paasng.accounts.permissions.application import application_perm_class
from paasng.engine.deploy.archive import OfflineManager
from paasng.engine.exceptions import OfflineOperationExistError
from paasng.engine.models.deployment import Deployment
from paasng.engine.models.offline import OfflineOperation
from paasng.engine.models.operations import ModuleEnvironmentOperations
from paasng.engine.serializers import (
    CreateOfflineOperationSLZ,
    OfflineOperationSLZ,
    OperationSLZ,
    QueryOperationsSLZ,
    ResourceMetricsSLZ,
)
from paasng.platform.applications.mixins import ApplicationCodeInPathMixin
from paasng.platform.environments.constants import EnvRoleOperation
from paasng.platform.environments.exceptions import RoleNotAllowError
from paasng.platform.environments.utils import env_role_protection_check
from paasng.utils.error_codes import error_codes

logger = logging.getLogger(__name__)


class OfflineViewset(viewsets.ViewSet, ApplicationCodeInPathMixin):
    """
    应用下线相关API
    基于stop process实现
    """

    serializer_class = CreateOfflineOperationSLZ
    permission_classes = [IsAuthenticated, application_perm_class(AppAction.BASIC_DEVELOP)]

    def offline(self, request, code, module_name, environment):
        """
        发起下线请求
        - /api/bkapps/applications/{code}/envs/{environment}/offlines/
        """
        application = self.get_application()
        module = application.get_module(module_name)

        serializer = CreateOfflineOperationSLZ(data=request.data)
        serializer.is_valid(raise_exception=True)

        app_environment = module.get_envs(environment)
        manager = OfflineManager(env=app_environment)

        roles = fetch_user_roles(application.code, request.user.username)
        try:
            # 现在部署和下架使用相同的操作识别
            env_role_protection_check(operation=EnvRoleOperation.DEPLOY.value, env=app_environment, roles=roles)
        except RoleNotAllowError:
            raise error_codes.RESTRICT_ROLE_DEPLOY_ENABLED

        try:
            offline_operation = manager.perform_env_offline(operator=request.user.pk)
        except Deployment.DoesNotExist:
            # 未曾部署，跳过该环境的下架操作
            raise error_codes.CANNOT_OFFLINE_APP.f(_("没有找到对应的部署记录，不允许下架"))
        except OfflineOperationExistError:
            # 在规定时间内，存在下架操作
            raise error_codes.CANNOT_OFFLINE_APP.f(_("存在正在进行的下架任务，请勿重复操作"))
        except Exception as e:
            logger.exception("app offline error")
            raise error_codes.CANNOT_OFFLINE_APP.f(str(e))
        else:
            result = {
                'offline_operation_id': offline_operation.id,
            }
            return JsonResponse(data=result, status=status.HTTP_201_CREATED)

    def get_offline_result(self, request, code, module_name, uuid):
        """
        查询下线任务结果
        - /api/bkapps/applications/{code})/offline_operations/{uuid}/result/
        - path param: code, app名
        - path param: uuid, 部署任务的uuid(即deployment_id)
        """
        application = self.get_application()
        module = application.get_module(module_name)

        try:
            offline_operation = OfflineOperation.objects.get(id=uuid, app_environment__module=module)
        except OfflineOperation.DoesNotExist:
            raise error_codes.CANNOT_GET_OFFLINE.f(_(f"{code} 没有id为 {uuid} 的下架记录"))
        else:
            data = OfflineOperationSLZ(instance=offline_operation).data
            return JsonResponse(data)

    @swagger_auto_schema(response_serializer=OfflineOperationSLZ)
    def get_resumable_offline_operations(self, request, code, module_name, environment):
        """查询可恢复的下架操作"""
        application = self.get_application()
        module = application.get_module(module_name)

        app_env = module.envs.get(environment=environment)
        try:
            offline_operation = OfflineOperation.objects.filter(app_environment=app_env).get_latest_resumable(
                max_resumable_seconds=settings.ENGINE_OFFLINE_RESUMABLE_SECS
            )
        except OfflineOperation.DoesNotExist:
            return Response({})

        serializer = OfflineOperationSLZ(instance=offline_operation)
        return Response({"result": serializer.data})


class OperationsViewset(viewsets.ViewSet, ApplicationCodeInPathMixin):
    """
    应用操作记录相关API
    比如：部署记录和下线记录
    """

    serializer_class = QueryOperationsSLZ
    permission_classes = [IsAuthenticated, application_perm_class(AppAction.BASIC_DEVELOP)]

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            from rest_framework.pagination import LimitOffsetPagination

            self._paginator = LimitOffsetPagination()
            self._paginator.default_limit = 12
        return self._paginator

    def list(self, request, code, module_name):
        """
        查询部署历史
        - /api/bkapps/applications/{code}/operations/lists/
        - get param: environment, 发布的环境, string
        - get param: operator, 操作者, string
        - get param: limit, 结果数量, integer
        - get param: offset, 翻页跳过数量, integer
        """
        application = self.get_application()
        module = application.get_module(module_name)

        serializer = QueryOperationsSLZ(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.data

        operations = ModuleEnvironmentOperations.objects.owned_by_module(
            module, environment=params.get('environment')
        ).order_by('-created')

        # Filter by operator if provided
        operator = params.get('operator')
        if operator:
            operator = user_id_encoder.encode(settings.USER_TYPE, operator)
            operations = operations.filter(operator=operator)

        # Paginator
        page = self.paginator.paginate_queryset(operations, self.request, view=self)
        serializer = OperationSLZ(page, many=True)
        return self.paginator.get_paginated_response(serializer.data)


class ProcessResourceMetricsViewset(viewsets.ViewSet, ApplicationCodeInPathMixin):
    """进程资源使用 Metrics API"""

    permission_classes = [IsAuthenticated, application_perm_class(AppAction.BASIC_DEVELOP)]

    @staticmethod
    def _format_datetime(date_string):
        # front page should follow this format
        return datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")

    @swagger_auto_schema(query_serializer=ResourceMetricsSLZ)
    def list(self, request, code, module_name, environment):
        """获取 instance metrics"""
        wl_app = self.get_wl_app_via_path()
        serializer = ResourceMetricsSLZ(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.data

        params = {
            'wl_app': wl_app,
            'process_type': data['process_type'],
            'query_metrics': data['query_metrics'],
            'time_range': MetricSmartTimeRange.from_request_data(data),
        }

        if data.get('instance_name'):
            params['instance_name'] = data['instance_name']
            get_metrics_method = list_app_proc_metrics
            ResultSLZ = ResourceMetricsResultSerializer
        else:
            get_metrics_method = list_app_proc_all_metrics  # type: ignore
            ResultSLZ = InstanceMetricsResultSerializer

        try:
            result = get_metrics_method(**params)
        except RequestMetricBackendError as e:
            raise error_codes.CANNOT_FETCH_RESOURCE_METRICS.f(str(e))
        except AppInstancesNotFoundError as e:
            raise error_codes.CANNOT_FETCH_RESOURCE_METRICS.f(str(e))
        except AppMetricNotSupportedError as e:
            raise error_codes.APP_METRICS_UNSUPPORTED.f(str(e))

        return Response(data={'result': ResultSLZ(instance=result, many=True).data})
