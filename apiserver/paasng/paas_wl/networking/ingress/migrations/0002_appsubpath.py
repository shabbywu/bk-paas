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
# Generated by Django 2.2.17 on 2021-02-02 06:22
from django.db import migrations, models
import django.db.models.deletion
from paasng.platform.core.storages.dbrouter import skip_if_found_record


# 由于架构调整, 该 DjangoApp 从 services 重命名为 ingress
# 为避免 migrations 重复执行, 使用 skip_if_found_record 声明该 migration 的历史名称
# 如果 django_migrations 表中存在重命名前的执行记录, 则跳过执行该 Migration
@skip_if_found_record(sentinel=("services", "0002_appsubpath"))
class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
        ('ingress', '0001_initial'),
    ]


    operations = [
        migrations.CreateModel(
            name='AppSubpath',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('region', models.CharField(max_length=32)),
                ('cluster_name', models.CharField(max_length=32)),
                ('subpath', models.CharField(max_length=128)),
                ('source', models.IntegerField()),
                ('app', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='api.App')),
            ],
            options={
                'unique_together': {('region', 'subpath')},
                'db_table': 'services_appsubpath',
            },
        ),
    ]
