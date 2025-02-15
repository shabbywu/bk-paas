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
from unittest import mock

import pytest

from paas_wl.cluster.models import Cluster
from paas_wl.cluster.utils import get_cluster_by_app
from tests.paas_wl.utils.wl_app import create_wl_app

pytestmark = pytest.mark.django_db(databases=["workloads"])


class TestGetClusterByApp:
    @pytest.fixture(autouse=True)
    def setup(self, example_cluster_config):
        clusters = [
            {
                "name": "region1-default",
                "region": "region-1",
                "is_default": True,
                **example_cluster_config,
            },
            {
                "name": "region2-default",
                "region": "region-2",
                "is_default": True,
                **example_cluster_config,
            },
            {
                "name": "region2-custom",
                "region": "region-2",
                "is_default": False,
                **example_cluster_config,
            },
        ]
        for cluster in clusters:
            Cluster.objects.register_cluster(**cluster)

        # 由于注册集群到 DB 后，未能刷新 _k8s_global_configuration_pool_map，
        # 导致创建 WlApp 后触发的信号处理逻辑中，无法获取到集群的 context，因此抛出 ValueError
        # 考虑到本处不获取集群 client，并不影响当前测试，因此通过 mock 处理
        with mock.patch(
            'paas_wl.platform.applications.models.managers.app_res_ver.get_client_by_app',
            new=lambda *args, **kwargs: None,
        ):
            yield

    def test_get_cluster_by_app_normal(self):
        app = create_wl_app(force_app_info={'region': 'region-2'})
        cluster = get_cluster_by_app(app)
        assert cluster.name == 'region2-default'

    def test_get_cluster_by_app_cluster_configured(self):
        app = create_wl_app(force_app_info={'region': 'region-2'})
        config = app.config_set.latest()
        config.cluster = 'region2-custom'
        config.save()

        cluster = get_cluster_by_app(app)
        assert cluster.name == 'region2-custom'
