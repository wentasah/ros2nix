# -*- coding: utf-8 -*-
#
# Copyright (c) 2016 David Bensoussan, Synapticon GmbH
# Copyright (c) 2019 Open Source Robotics Foundation, Inc.
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal  in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
from operator import attrgetter
from textwrap import dedent, indent
from time import gmtime, strftime
from typing import Iterable, Set, Optional, List

from superflore.utils import get_license


def _escape_nix_string(string: str):
    return '"{}"'.format(string.replace("\\", "\\\\").replace("${", r"\${").replace('"', r"\""))


class NixLicense:
    """
    Converts a ROS license to the correct Nix license attribute.
    """

    _LICENSE_MAP = {
        '3-Clause-BSD': 'bsd3',
        'AGPL-3.0-only': 'agpl3Only',
        'AGPLv3': 'agpl3Only',
        'ASL 2.0': 'asl20',
        'Apache-2': 'asl20',
        'Apache-2.0': 'asl20',
        'Apache-2.0-License': 'asl20',
        'Apache-Licence-2.0': 'asl20',
        'Apache-license-2.0': 'asl20',
        'BSD': 'bsdOriginal',
        'BSD-2': 'bsd2',
        'BSD-2-Clause': 'bsd2',
        'BSD-2-clause': 'bsd2',
        'BSD-3-Clause': 'bsd3',
        'BSD-3-Clause-License': 'bsd3',
        'BSD-3-clause': 'bsd3',
        'BSD-Clause-3': 'bsd3',  # Used in rqt_gauges
        'BSD-License-2.0': 'bsd3',  # In teleop_twist_keyboard, BSD-License-2.0 is almost exactly bsd3. The only difference is use of "copyright owner" instead of "copyright holder".
        'BSL-1.0': 'boost',
        'Boost-1.0': 'boost',
        'CC-BY-NC-ND-4.0': 'cc-by-nc-nd-40',
        'CC-BY-NC-SA-3.0': 'cc-by-nc-sa-30',
        'CC-BY-NC-SA-4.0': 'cc-by-nc-sa-40',
        'CC-BY-SA-4.0': 'cc-by-sa-40',
        'CC0': 'cc0',
        'CC0-1.0': 'cc0',
        'EPL-2.0': 'epl20',
        'Eclipse-Distribution-License-1.0': 'bsd3',  # see https://www.eclipse.org/org/documents/edl-v10/
        'GPL-1': 'gpl1',
        'GPL-2': 'gpl2',
        'GPL-2.0-only': 'gpl2Only',
        'GPL-2.0-or-later': 'gpl2Plus',
        'GPL-3': 'gpl3',
        'GPL-3.0': "gpl3",
        'GPL-3.0-only': 'gpl3Only',
        'GPLv2-license': 'gpl2Only',
        'HPND': 'hpnd',
        'LGPL-2': 'lgpl2',
        'LGPL-2.1': 'lgpl21',
        'LGPL-2.1-only': 'lgpl21Only',
        'LGPL-2.1-or-later': 'lgpl21Plus',
        'LGPL-3': 'lgpl3',
        'LGPL-3.0': 'lgpl3Only',
        'LGPL-3.0-only': 'lgpl3Only',
        'LGPL-v3': 'lgpl3Only',
        'MIT': 'mit',
        'MIT-0': 'mit0',
        'MPL-1.0': 'mpl10',
        'MPL-1.1': 'mpl11',
        'MPL-2.0': 'mpl20',
        'MPL-2.0-license': 'mpl20',
        'Mozilla-Public-License-2.0': 'mpl20',
        'PD': 'publicDomain',
        'Zlib': 'zlib',
        'Zlib-License': 'zlib',
        'apache-2.0': 'asl20',
    }

    def __init__(self, name):
        try:
            name = get_license(name)
            self.name = self._LICENSE_MAP[name]
            self.custom = False
        except KeyError:
            self.name = name
            self.custom = True

    @property
    def nix_code(self) -> str:
        if self.custom:
            return _escape_nix_string(self.name)
        else:
            return self.name


class NixExpression:
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        licenses: Iterable[NixLicense],
        distro_name: str,
        name_format: str,
        build_type: str,
        src_expr: str,
        name_param: Optional[str] = None,
        version_param: Optional[str] = None,
        build_inputs: Set[str] = set(),
        propagated_build_inputs: Set[str] = set(),
        check_inputs: Set[str] = set(),
        native_build_inputs: Set[str] = set(),
        propagated_native_build_inputs: Set[str] = set(),
        src_param: Optional[str] = None,
        source_root: Optional[str] = None,
        do_check: Optional[bool] = None,
        patches: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.version = version
        self.src_param = src_param
        self.src_expr = src_expr
        self.patches = patches
        self.source_root = source_root
        self.do_check = do_check

        self.name_param = name_param
        self.version_param = version_param

        self.description = description
        self.licenses = licenses
        self.distro_name = distro_name
        self.name_format = name_format
        self.build_type = build_type

        self.build_inputs = build_inputs
        self.propagated_build_inputs = propagated_build_inputs
        self.check_inputs = check_inputs
        self.native_build_inputs = native_build_inputs
        self.propagated_native_build_inputs = propagated_native_build_inputs

    @staticmethod
    def _to_nix_list(it: Iterable[str]) -> str:
        return '[ ' + ' '.join(it) + ' ]'

    @staticmethod
    def _to_nix_parameter(dep: str) -> str:
        return dep.split('.')[0]

    def get_text(self, distributor: Optional[str], license_name: Optional[str]) -> str:
        """
        Generate the Nix expression, given the distributor line
        and the license text.
        """

        ret = []

        if distributor or license_name:
            ret += dedent('''
            # Copyright {} {}
            # Distributed under the terms of the {} license

            ''').format(strftime("%Y", gmtime()), distributor, license_name)

        args = ["lib", "buildRosPackage"]

        if self.name_param:
            args.append(self.name_param)

        if self.version_param:
            args.append(self.version_param)

        if self.src_param:
            args.append(self.src_param)

        src = indent(self.src_expr, "  ").strip()

        args.extend(
            sorted(
                set(
                    map(
                        self._to_nix_parameter,
                        self.build_inputs
                        | self.propagated_build_inputs
                        | self.check_inputs
                        | self.native_build_inputs
                        | self.propagated_native_build_inputs,
                    )
                )
            )
        )
        ret += '{ ' + ', '.join(args) + ' }:'

        # To prevent issues with infinite recursion, use inherit if the name
        # matches the passed param
        def assign_attr(name, val):
            return f"{name} = {val}" if name != val else f"inherit {name}"

        ret += dedent(f'''
        buildRosPackage rec {{
          {assign_attr("pname", self.name_param or f'"{self.name_format.format(distro=self.distro_name, package_name=self.name)}"')};
          {assign_attr("version", self.version_param or f'"{self.version}"')};

          {assign_attr("src", src)};

          buildType = "{self.build_type}";
        ''')
        if self.patches:
            ret += f"""  patches = [\n    {"\n    ".join(self.patches)}\n  ];\n"""

        if self.source_root:
            ret += f'  sourceRoot = "{self.source_root}";\n'

        if self.do_check is not None:
            ret += f'  doCheck = {"true" if self.do_check else "false"};\n'

        if self.build_inputs:
            ret += "  buildInputs = {};\n".format(self._to_nix_list(sorted(self.build_inputs)))

        if self.check_inputs:
            ret += "  checkInputs = {};\n".format(self._to_nix_list(sorted(self.check_inputs)))

        if self.propagated_build_inputs:
            ret += "  propagatedBuildInputs = {};\n".format(
                self._to_nix_list(sorted(self.propagated_build_inputs))
            )

        if self.native_build_inputs:
            ret += "  nativeBuildInputs = {};\n".format(
                self._to_nix_list(sorted(self.native_build_inputs))
            )

        if self.propagated_native_build_inputs:
            ret += "  propagatedNativeBuildInputs = {};\n".format(
                self._to_nix_list(sorted(self.propagated_native_build_inputs))
            )

        ret += dedent('''
          meta = {{
            description = {};
            license = with lib.licenses; {};
          }};
        }}
        ''').format(
            _escape_nix_string(self.description),
            self._to_nix_list(map(attrgetter('nix_code'), self.licenses)),
        )

        return ''.join(ret)
