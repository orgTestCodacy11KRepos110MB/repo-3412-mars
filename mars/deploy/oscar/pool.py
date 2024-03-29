# Copyright 1999-2021 Alibaba Group Holding Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Dict, List

from ... import oscar as mo
from ...resource import cuda_count, Resource


def _need_suspend_sigint() -> bool:
    try:
        from IPython import get_ipython

        return get_ipython() is not None
    except ImportError:
        return False


async def create_supervisor_actor_pool(
    address: str,
    n_process: int,
    modules: List[str] = None,
    ports: List[int] = None,
    subprocess_start_method: str = None,
    **kwargs,
):
    return await mo.create_actor_pool(
        address,
        n_process=n_process,
        ports=ports,
        modules=modules,
        subprocess_start_method=subprocess_start_method,
        suspend_sigint=_need_suspend_sigint(),
        **kwargs,
    )


async def create_worker_actor_pool(
    address: str,
    band_to_resource: Dict[str, Resource],
    n_io_process: int = 1,
    modules: List[str] = None,
    ports: List[int] = None,
    cuda_devices: List[int] = None,
    subprocess_start_method: str = None,
    **kwargs,
):
    # TODO: support NUMA when ready
    n_process = sum(
        int(resource.num_cpus) or int(resource.num_gpus)
        for resource in band_to_resource.values()
    )
    envs = []
    labels = ["main"]

    if cuda_devices is None:  # pragma: no cover
        env_devices = os.environ.get("CUDA_VISIBLE_DEVICES")
        if not env_devices:
            cuda_devices = list(range(cuda_count()))
        else:
            cuda_devices = [int(i) for i in env_devices.split(",")]

    i_gpu = iter(sorted(cuda_devices))
    for band, resource in band_to_resource.items():
        if band.startswith("gpu"):  # pragma: no cover
            idx = str(next(i_gpu))
            envs.append({"CUDA_VISIBLE_DEVICES": idx})
            labels.append(f"gpu-{idx}")
        else:
            assert band.startswith("numa")
            num_cpus = int(resource.num_cpus)
            envs.extend([dict() for _ in range(num_cpus)])
            labels.extend([band] * num_cpus)

    return await mo.create_actor_pool(
        address,
        n_process=n_process,
        ports=ports,
        n_io_process=n_io_process,
        labels=labels,
        envs=envs,
        modules=modules,
        subprocess_start_method=subprocess_start_method,
        suspend_sigint=_need_suspend_sigint(),
        **kwargs,
    )
