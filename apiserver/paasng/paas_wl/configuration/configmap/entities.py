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
from dataclasses import dataclass
from typing import Dict, Optional

from kubernetes.dynamic import ResourceInstance

from paas_wl.platform.applications.models import WlApp
from paas_wl.resources.base.kres import KConfigMap
from paas_wl.resources.kube_res.base import AppEntity, AppEntityDeserializer, AppEntityManager, AppEntitySerializer


class ConfigMapSerializer(AppEntitySerializer['ConfigMap']):
    api_version = 'v1'

    def serialize(self, obj: 'ConfigMap', original_obj: Optional[ResourceInstance] = None, **kwargs) -> Dict:
        return {
            'apiVersion': self.api_version,
            'kind': 'ConfigMap',
            'metadata': {
                'name': obj.name,
                'namespace': obj.app.namespace,
            },
            'data': obj.data,
        }


class ConfigMapDeserializer(AppEntityDeserializer['ConfigMap']):
    def deserialize(self, app: WlApp, kube_data: ResourceInstance) -> 'ConfigMap':
        return ConfigMap(
            app=app,
            name=kube_data.metadata.name,
            data=kube_data.data,
        )


@dataclass
class ConfigMap(AppEntity):
    data: str

    class Meta:
        kres_class = KConfigMap
        deserializer = ConfigMapDeserializer
        serializer = ConfigMapSerializer


configmap_kmodel: AppEntityManager[ConfigMap] = AppEntityManager[ConfigMap](ConfigMap)
