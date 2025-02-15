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
import operator
from typing import Callable, Dict, Generator, Iterable, Iterator, List, NamedTuple, Optional, TypeVar, cast

from django.db.models import QuerySet
from django.http import Http404

from paasng.dev_resources.servicehub.constants import ServiceBindingType, ServiceType
from paasng.dev_resources.servicehub.exceptions import (
    DuplicatedServiceBoundError,
    ServiceObjNotFound,
    SvcAttachmentDoesNotExist,
)
from paasng.dev_resources.servicehub.local.manager import LocalPlanMgr, LocalServiceMgr, LocalServiceObj
from paasng.dev_resources.servicehub.models import (
    LocalServiceDBProperties,
    RemoteServiceDBProperties,
    ServiceDBProperties,
)
from paasng.dev_resources.servicehub.remote.manager import RemotePlanMgr, RemoteServiceMgr, RemoteServiceObj
from paasng.dev_resources.servicehub.remote.store import get_remote_store
from paasng.dev_resources.servicehub.services import EngineAppInstanceRel, PlanObj, ServiceObj
from paasng.dev_resources.services.models import ServiceCategory
from paasng.engine.models import EngineApp
from paasng.platform.modules.models import Module
from paasng.platform.region.models import get_all_regions, set_service_categories_loader

logger = logging.getLogger(__name__)


def _fetch_service_categories(region: str) -> List[ServiceCategory]:
    """Fetch service categories by region."""
    category_ids = {obj.category_id for obj in mixed_service_mgr.list_by_region(region)}
    categories = ServiceCategory.objects.filter(pk__in=category_ids).order_by("-sort_priority")
    return list(categories)


set_service_categories_loader(_fetch_service_categories)


def _proxied_svc_dispatcher(method_name: str):
    """Dispatch a method call by service type"""

    def func(self, service: ServiceObj, *args, **kwargs):
        for mgr in self.mgr_instances:
            if isinstance(service, mgr.service_obj_cls):
                method = getattr(mgr, method_name)
                return method(service, *args, **kwargs)
        raise ValueError(f'{service} is an invalid service')

    return func


def _proxied_chained_generator(method_name: str):
    def func(self, *args, **kwargs):
        for mgr in self.mgr_instances:
            method = getattr(mgr, method_name)
            yield from method(*args, **kwargs)

    return func


class SharedServiceInfo(NamedTuple):
    """Shared service information object

    :param service: Shared service object
    :param module: Module which shares service from other modules
    :param ref_module: Module which was referenced(shared)
    """

    service: ServiceObj
    module: Module
    ref_module: Module


def get_db_properties(service: ServiceObj) -> ServiceDBProperties:
    """Get database properties object by service"""
    if isinstance(service, RemoteServiceObj):
        return RemoteServiceDBProperties()
    elif isinstance(service, LocalServiceObj):
        return LocalServiceDBProperties()
    raise ValueError(f'Unknown service obj type: {type(service)}')


def get_db_properties_by_service_type(service_type: str) -> ServiceDBProperties:
    """Get database properties object by service type"""
    if service_type == ServiceType.REMOTE:
        return RemoteServiceDBProperties()
    elif service_type == ServiceType.LOCAL:
        return LocalServiceDBProperties()
    raise ValueError(f'Unknown service type: {service_type}')


T = TypeVar('T', bound='MixedServiceMgr')


class MixedServiceMgr:
    """A hub for managing services of mixed sources: database and remote REST services"""

    def __init__(self):
        store = get_remote_store()
        self.mgr_instances = [LocalServiceMgr(), RemoteServiceMgr(store)]

    def get(self, uuid: str, region: str) -> ServiceObj:
        for mgr in self.mgr_instances:
            try:
                return mgr.get(uuid, region)
            except ServiceObjNotFound:
                continue
        raise ServiceObjNotFound(f"service with uuid {uuid} in region {region} was not found")

    def find_by_name(self, name: str, region: str, include_invisible: bool = False) -> ServiceObj:
        for mgr in self.mgr_instances:
            try:
                obj = mgr.find_by_name(name, region)
                if include_invisible or obj.is_visible:
                    return obj
            except ServiceObjNotFound:
                continue
        raise ServiceObjNotFound(f"service with name {name} in region {region} was not found")

    def get_without_region(self, uuid: str) -> ServiceObj:
        """Get a service without any region info"""
        for region in get_all_regions().keys():
            try:
                return self.get(uuid, region)
            except ServiceObjNotFound:
                continue
        raise ServiceObjNotFound(f"service with uuid {uuid} was not found")

    def get_or_404(self, *args, **kwargs) -> ServiceObj:
        """Get a ServiceObj object or raise 404

        :raises: Http404 if service was not found
        """
        try:
            return self.get(*args, **kwargs)
        except ServiceObjNotFound:
            raise Http404

    def get_module_rel(self, service_id: str, module_id: str):
        for mgr in self.mgr_instances:
            try:
                rel = mgr.get_module_rel(service_id=service_id, module_id=module_id)
            except SvcAttachmentDoesNotExist:
                # 由于 remote service 没有真正的建模，所以这里不容易直接判断是否真正存在，故略过
                logger.info(f"module<{module_id}> has no attachment with service<{service_id}>, try next mgr")
                continue
            else:
                return rel
        # 所有 mgr 都无法找到具体条目
        raise SvcAttachmentDoesNotExist(f"module<{module_id}> has no attachment with service<{service_id}>")

    def bind_service(self, service: ServiceObj, module: Module, specs: Optional[Dict[str, str]] = None) -> str:
        """Create bind relationship for given module and service object"""
        DuplicatedBindingValidator(module, ServiceBindingType.NORMAL).validate(service)
        return _proxied_svc_dispatcher('bind_service')(self, service, module, specs=specs)

    # Dispatch via service type start

    get_attachment_by_instance_id = _proxied_svc_dispatcher('get_attachment_by_instance_id')
    get_instance_rel_by_instance_id = cast(
        Callable[..., EngineAppInstanceRel], _proxied_svc_dispatcher('get_instance_rel_by_instance_id')
    )
    get_provisioned_queryset = _proxied_svc_dispatcher('get_provisioned_queryset')
    module_is_bound_with = _proxied_svc_dispatcher('module_is_bound_with')
    update = _proxied_svc_dispatcher("update")
    destroy = _proxied_svc_dispatcher("destroy")

    def get_provisioned_queryset_by_services(self, services: List[ServiceObj], application_ids: List[str]) -> QuerySet:
        joined_qs = None
        for mgr in self.mgr_instances:
            mgr_services = [service for service in services if isinstance(service, mgr.service_obj_cls)]
            if not mgr_services:
                continue

            qs = mgr.get_provisioned_queryset_by_services(mgr_services, application_ids)
            if joined_qs is None:
                joined_qs = qs
            else:
                joined_qs = joined_qs.union(qs)
        if joined_qs is None:
            raise ValueError(f'{services} is an invalid service list')
        return joined_qs

    # Dispatch via service type end

    # Proxied generator methods start

    list_by_category = _proxied_chained_generator('list_by_category')
    list_binded: Callable[..., Iterable['ServiceObj']] = _proxied_chained_generator('list_binded')
    list_all_rels = cast(
        Callable[..., Generator[EngineAppInstanceRel, None, None]], _proxied_chained_generator('list_all_rels')
    )
    list_unprovisioned_rels = cast(
        Callable[..., Iterator[EngineAppInstanceRel]], _proxied_chained_generator('list_unprovisioned_rels')
    )
    list_provisioned_rels = cast(
        Callable[..., Iterable[EngineAppInstanceRel]], _proxied_chained_generator('list_provisioned_rels')
    )
    list_by_region: Callable[..., Iterable[ServiceObj]] = _proxied_chained_generator('list_by_region')
    list = cast(Callable[..., Iterable[ServiceObj]], _proxied_chained_generator('list'))

    # Proxied generator methods end

    def get_env_vars(self, engine_app: EngineApp, service: Optional[ServiceObj] = None) -> Dict[str, str]:
        """Get all provisioned services env variables

        :param engine_app: EngineApp object
        :param service: Optional service object. if given, will only return credentials of the specified service,
            otherwise return the credentials of all services.
        :returns: Dict of env variables.
        """
        instances = [rel.get_instance() for rel in self.list_provisioned_rels(engine_app, service=service)]
        # 新的覆盖旧的
        instances.sort(key=operator.attrgetter('create_time'))

        result = {}
        for i in instances:
            result.update(i.credentials)
        return result


class MixedPlanMgr:
    """A hub for managing plans of mixed sources: database and remote REST plans"""

    def __init__(self):
        store = get_remote_store()
        self.mgr_instances = [LocalPlanMgr(), RemotePlanMgr(store)]

    list = cast(Callable[..., Generator[PlanObj, None, None]], _proxied_chained_generator("list_plans"))
    create = _proxied_svc_dispatcher("create_plan")
    update = _proxied_svc_dispatcher("update_plan")
    delete = _proxied_svc_dispatcher("delete_plan")


mixed_service_mgr = MixedServiceMgr()
mixed_plan_mgr = MixedPlanMgr()


class DuplicatedBindingValidator:
    """Validate duplicated service bindings

    :param module: Module which is trying to create new binding relationship
    :param current_type: Type of current service binding
    """

    def __init__(self, module: Module, current_type: ServiceBindingType):
        self.module = module
        self.current_type = current_type

    def validate(self, service: ServiceObj) -> None:
        """Raise error when try to bind and share a service in the same time

        :raises: DuplicatedServiceBoundError when validation fails
        """
        if self.current_type == ServiceBindingType.NORMAL:
            self._check_duplicated_sharing(service)
        elif self.current_type == ServiceBindingType.SHARING:
            self._check_duplicated_normal(service)

    def _check_duplicated_normal(self, service: ServiceObj):
        if service in mixed_service_mgr.list_binded(self.module):
            raise DuplicatedServiceBoundError(f'Module: {self.module.name} already bound with service {service.name}')

    def _check_duplicated_sharing(self, service: ServiceObj):
        from .sharing import ServiceSharingManager

        infos = ServiceSharingManager(self.module).list_all_shared_info()
        for info in infos:
            if info.service == service:
                raise DuplicatedServiceBoundError(
                    f'Module: {self.module.name} already shared an attachment in service: {service.name}'
                )
