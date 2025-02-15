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
# Generated by Django 3.2.12 on 2023-05-30 08:04

from django.db import migrations, models
import django.db.models.deletion
import paasng.engine.constants
import paasng.platform.modules.models.deploy_config
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0007_module_runtime_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='BuildConfig',
            fields=[
                ('uuid', models.UUIDField(auto_created=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True, verbose_name='UUID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('build_method', models.CharField(default=paasng.engine.constants.RuntimeType['BUILDPACK'], max_length=32, verbose_name='构建方式')),
                ('dockerfile_path', models.CharField(help_text='Dockerfile文件路径, 必须保证 Dockerfile 在构建目录下, 填写时无需包含构建目录', max_length=512, null=True)),
                ('docker_build_args', paasng.platform.modules.models.deploy_config.DockerBuildArgsField(default=dict)),
                ('tag_options', paasng.platform.modules.models.deploy_config.ImageTagOptionsField(default=paasng.platform.modules.models.deploy_config.ImageTagOptions)),
                ('buildpack_builder', models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='modules.appslugbuilder')),
                ('buildpack_runner', models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='modules.appslugrunner')),
                ('buildpacks', models.ManyToManyField(null=True, related_name='related_build_configs', to='modules.AppBuildPack')),
                ('module', models.OneToOneField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='build_config', to='modules.module')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
