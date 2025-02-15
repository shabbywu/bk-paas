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
from paas_wl.cnative.specs.constants import (
    BKAPP_CODE_ANNO_KEY,
    ENVIRONMENT_ANNO_KEY,
    MODULE_NAME_ANNO_KEY,
    RESOURCE_TYPE_KEY,
    WLAPP_NAME_ANNO_KEY,
)
from paas_wl.platform.applications.models.managers.app_metadata import get_metadata
from paas_wl.resources.base.kres import KDeployment, KPod, KReplicaSet
from paas_wl.utils.basic import digest_if_length_exceeded

from .mapper import CallThroughKresMapper, MapperField, MapperPack


class PodMapper(CallThroughKresMapper[KPod]):
    kres_class = KPod

    @property
    def name(self) -> str:
        return f"{self.process.app.scheduler_safe_name}--{self.process.type}"

    @property
    def pod_selector(self) -> str:
        return digest_if_length_exceeded(f"{self.process.app.name}-{self.process.type}", 63)

    @property
    def labels(self) -> dict:
        mdata = get_metadata(self.process.app)
        return {
            "pod_selector": self.pod_selector,
            "release_version": str(self.process.version),
            "region": self.process.app.region,
            "app_code": mdata.get_paas_app_code(),
            "module_name": mdata.module_name,
            "env": mdata.environment,
            "process_id": self.process.type,
            "category": "bkapp",
            "mapper_version": "v2",
            # 新 labels
            BKAPP_CODE_ANNO_KEY: mdata.get_paas_app_code(),
            MODULE_NAME_ANNO_KEY: mdata.module_name,
            ENVIRONMENT_ANNO_KEY: mdata.environment,
            WLAPP_NAME_ANNO_KEY: self.process.app.name,
            RESOURCE_TYPE_KEY: "process",
        }

    @property
    def match_labels(self) -> dict:
        return dict(
            pod_selector=self.pod_selector,
        )


class DeploymentMapper(CallThroughKresMapper[KDeployment]):
    kres_class = KDeployment

    @property
    def pod_selector(self) -> str:
        return digest_if_length_exceeded(f"{self.process.app.name}-{self.process.type}", 63)

    @property
    def labels(self) -> dict:
        mdata = get_metadata(self.process.app)
        return {
            "pod_selector": self.pod_selector,
            "release_version": str(self.process.version),
            "region": self.process.app.region,
            "app_code": mdata.get_paas_app_code(),
            "module_name": mdata.module_name,
            "env": mdata.environment,
            "process_id": self.process.type,
            "category": "bkapp",
            "mapper_version": "v2",
            # 云原生应用新增的 labels
            BKAPP_CODE_ANNO_KEY: mdata.get_paas_app_code(),
            MODULE_NAME_ANNO_KEY: mdata.module_name,
            ENVIRONMENT_ANNO_KEY: mdata.environment,
            WLAPP_NAME_ANNO_KEY: self.process.app.name,
            RESOURCE_TYPE_KEY: "process",
        }

    @property
    def match_labels(self) -> dict:
        return dict(
            pod_selector=self.pod_selector,
        )

    @property
    def name(self) -> str:
        return f"{self.process.app.scheduler_safe_name}--{self.process.type}"


class ReplicaSetMapper(CallThroughKresMapper[KReplicaSet]):
    kres_class = KReplicaSet

    @property
    def pod_selector(self) -> str:
        return digest_if_length_exceeded(f"{self.process.app.name}-{self.process.type}", 63)

    @property
    def name(self) -> str:
        return f"{self.process.app.scheduler_safe_name}--{self.process.type}"

    @property
    def match_labels(self) -> dict:
        return dict(
            pod_selector=self.pod_selector,
        )


class V2Mapper(MapperPack):
    version = "v2"
    _ignore_command_name = True
    pod: MapperField[KPod] = MapperField(PodMapper)
    deployment: MapperField[KDeployment] = MapperField(DeploymentMapper)
    replica_set: MapperField[KReplicaSet] = MapperField(ReplicaSetMapper)
