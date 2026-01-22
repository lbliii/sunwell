# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Core Thesis Verification Tests.

These tests verify Sunwell's fundamental claims:

1. **DAG Synthesis**: Given any goal, synthesize a valid artifact DAG
2. **Quality Gates**: Execution respects confidence thresholds
3. **Provenance**: Every output is traceable to its inputs
4. **The Prism Principle**: Multi-perspective synthesis beats single-shot,
   especially on small models

If these tests fail, Sunwell's architecture is aspirational, not real.
"""
