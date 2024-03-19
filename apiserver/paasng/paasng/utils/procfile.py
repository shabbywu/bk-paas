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
import shlex
from typing import List


def generate_bash_command_with_tokens(command: List[str], args: List[str]) -> str:
    token_size = len(command) + len(args)
    script = r'"$(eval echo \"$0\")"'
    for i in range(1, token_size):
        script += rf' "$(eval echo \"${{{i}}}\")"'
    script_args = ""
    for s in command + args:
        script_args += f" {shlex.quote(s)}"
    return f"exec bash -c '{script}' {script_args.lstrip()}"
