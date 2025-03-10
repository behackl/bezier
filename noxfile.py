# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import glob
import os
import pathlib
import shutil
import sys

import nox
import nox.sessions
import py.path


nox.options.error_on_external_run = True
nox.options.error_on_missing_interpreters = True

IS_LINUX = sys.platform in ("linux", "linux2")
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = os.name == "nt"
DEPS = {
    "black": "black >= 22.1.0",
    "cmake-format": "cmake-format >= 0.6.13",
    "cmake": "cmake >= 3.21.4",
    "coverage": "coverage",
    "Cython": "Cython >= 0.29.27",
    "docutils": "docutils",
    "flake8": "flake8",
    "flake8-import-order": "flake8-import-order",
    "jsonschema": "jsonschema >= 4.2.1",
    "lcov_cobertura": "lcov_cobertura >= 1.6",
    "machomachomangler": "machomachomangler == 0.0.1",
    "matplotlib": "matplotlib >= 3.4.3",
    "numpy": "numpy >= 1.21.4",
    "pycobertura": "pycobertura >= 2.1.0",
    "Pygments": "Pygments",
    "pylint": "pylint >= 2.12.1",
    "pytest": "pytest >= 6.2.5",
    "pytest-cov": "pytest-cov",
    "scipy": "scipy >= 1.7.2",
    "sympy": "sympy >= 1.9",
    "seaborn": "seaborn >= 0.11.2",
}
BASE_DEPS = (DEPS["numpy"], DEPS["pytest"])
NOX_DIR = os.path.abspath(os.path.dirname(__file__))
DOCS_DEPS = (
    "--requirement",
    os.path.join(NOX_DIR, "docs", "requirements.txt"),
)
DEFAULT_INTERPRETER = "3.10"
PYPY = "pypy3"
ALL_INTERPRETERS = (
    "3.8",
    "3.8-32",
    "3.9",
    "3.9-32",
    "3.10",
    "3.10-32",
    PYPY,
)
BUILD_TYPE_DEBUG = "Debug"
BUILD_TYPE_RELEASE = "Release"
DEBUG_SESSION_NAME = "libbezier-debug"
RELEASE_SESSION_NAME = "libbezier-release"
INSTALL_PREFIX_ENV = "BEZIER_INSTALL_PREFIX"
WHEEL_ENV = "BEZIER_WHEEL"
DLL_HASH_ENV = "BEZIER_DLL_HASH"


def get_path(*names):
    return os.path.join(NOX_DIR, *names)


def is_wheelhouse(directory):
    if directory is None:
        return False

    as_path = pathlib.Path(directory)
    if not as_path.is_dir():
        return False

    wheels = list(as_path.glob("*.whl"))
    # NOTE: This could also be done by using ``next()`` instead of ``list()``
    #       and catching a ``StopIteration`` if empty.
    return len(wheels) > 0


def get_wheelhouse():
    candidates = (
        os.environ.get("WHEELHOUSE"),
        pathlib.Path.home() / "wheelhouse",
        pathlib.Path(os.path.abspath(os.sep)) / "wheelhouse",
    )

    for directory in candidates:
        if is_wheelhouse(directory):
            return directory

    return None


def pypy_setup(local_deps, session):
    wheelhouse = get_wheelhouse()
    if wheelhouse is not None:
        # Remove NumPy from dependencies.
        local_deps = list(local_deps)
        local_deps.remove(DEPS["numpy"])
        local_deps = tuple(local_deps)
        # Install NumPy and SciPy from pre-built wheels. Don't use ``DEPS``
        # to specify version range for NumPy and SciPy.
        session.install(
            "--no-index", "--find-links", str(wheelhouse), "numpy", "scipy"
        )
    return local_deps


def install_bezier(session, debug=False, env=None):
    if env is None:
        env = {}

    if debug:
        install_prefix = _cmake(session, BUILD_TYPE_DEBUG)
    else:
        install_prefix = _cmake(session, BUILD_TYPE_RELEASE)
    env[INSTALL_PREFIX_ENV] = install_prefix

    session.install(".", env=env)
    return install_prefix


@nox.session(py=DEFAULT_INTERPRETER)
@nox.parametrize("check", [True, False])
def update_generated(session, check):
    # Install all dependencies.
    session.install(DEPS["Cython"])
    if check:
        command = get_path("scripts", "remove_cython_files.py")
        session.run("python", command)

    pyx_file = get_path("src", "python", "bezier", "_speedup.pyx")
    session.run("cython", pyx_file)

    command = get_path("scripts", "clean_cython.py")
    c_glob = get_path("src", "python", "bezier", "*.c")
    for c_source in glob.glob(c_glob):
        session.run(
            "python",
            command,
            "--filename",
            c_source,
            "--virtualenv-dirname",
            os.path.basename(session.virtualenv.location),
        )
    if check:
        command = get_path("scripts", "cython_update_check.py")
        session.run("python", command)


@nox.session(py=ALL_INTERPRETERS)
def unit(session):
    interpreter = session.virtualenv.interpreter
    unit_deps = BASE_DEPS + (DEPS["sympy"],)
    if interpreter == PYPY:
        local_deps = pypy_setup(unit_deps, session)
    elif IS_WINDOWS and interpreter == "3.10-32":
        # The SciPy project hasn't yet shipped a wheel supporting 32-bit
        # Python 3.10 on Windows.
        # See: https://github.com/dhermes/bezier/issues/274
        local_deps = unit_deps
    else:
        local_deps = unit_deps + (DEPS["scipy"],)

    # Install all test dependencies.
    session.install(*local_deps)
    # Install this package.
    install_bezier(session, debug=True)
    # Run pytest against the unit tests.
    run_args = (
        ["python", "-m", "pytest"]
        + session.posargs
        + [get_path("tests", "unit")]
    )
    session.run(*run_args)


@nox.session(py=DEFAULT_INTERPRETER)
def cover(session):
    # Install all test dependencies.
    local_deps = BASE_DEPS + (
        DEPS["scipy"],
        DEPS["sympy"],
        DEPS["pytest-cov"],
        DEPS["coverage"],
    )
    session.install(*local_deps)
    # Install this package.
    install_bezier(session, debug=True)
    # Run pytest with coverage against the unit tests.
    run_args = ["python", "-m", "pytest", "--cov=bezier", "--cov=tests.unit"]
    run_args += session.posargs
    run_args += [get_path("tests", "unit")]
    session.run(*run_args)


@nox.session(py=ALL_INTERPRETERS)
def functional(session):
    interpreter = session.virtualenv.interpreter
    if interpreter == PYPY:
        local_deps = pypy_setup(BASE_DEPS, session)
    else:
        local_deps = BASE_DEPS

    # Install all test dependencies.
    session.install(*local_deps)
    # Install this package.
    install_bezier(session, debug=True)
    # Run pytest against the functional tests.
    run_args = (
        ["python", "-m", "pytest"]
        + session.posargs
        + [get_path("tests", "functional")]
    )
    session.run(*run_args)


@nox.session(py=DEFAULT_INTERPRETER)
def docs(session):
    # Install all dependencies.
    session.install(*DOCS_DEPS)
    # Install this package.
    install_bezier(session, env={"BEZIER_NO_EXTENSION": "True"})
    # Run the script for building docs.
    command = get_path("scripts", "build_docs.sh")
    session.run(command, external=True)


def get_doctest_args(session):
    run_args = [
        "sphinx-build",
        "-W",
        "-b",
        "doctest",
        "-d",
        get_path("docs", "build", "doctrees"),
        get_path("docs"),
        get_path("docs", "build", "doctest"),
    ]
    run_args += session.posargs
    return run_args


@nox.session(py=DEFAULT_INTERPRETER)
def doctest(session):
    # Install all dependencies.
    session.install(DEPS["sympy"], *DOCS_DEPS)
    # Install this package.
    if IS_MACOS:
        install_prefix = _cmake(session, BUILD_TYPE_RELEASE)
        command = get_path("scripts", "macos", "nox-install-for-doctest.sh")
        env = {INSTALL_PREFIX_ENV: install_prefix}
        session.run(command, external=True, env=env)
    elif IS_LINUX:
        command = get_path("scripts", "nox-install-for-doctest-linux.sh")
        session.run(command, external=True)
        install_prefix = _cmake(session, BUILD_TYPE_RELEASE)
    elif IS_WINDOWS:
        session.install(DEPS["machomachomangler"])
        install_prefix = install_bezier(
            session, env={WHEEL_ENV: "true", DLL_HASH_ENV: "e5dbb97a"}
        )
    else:
        raise OSError("Unknown operating system")

    # Run the script for building docs and running doctests.
    run_args = get_doctest_args(session)
    # Make sure that the root directory is on the Python path so that
    # ``tests`` is import-able.
    env = {"PYTHONPATH": get_path(), INSTALL_PREFIX_ENV: install_prefix}
    session.run(*run_args, env=env)


@nox.session(py=DEFAULT_INTERPRETER)
def docs_images(session):
    # Install all dependencies.
    local_deps = DOCS_DEPS
    local_deps += (
        DEPS["matplotlib"],
        DEPS["pytest"],
        DEPS["seaborn"],
        DEPS["sympy"],
    )
    session.install(*local_deps)
    # Install this package.
    if IS_MACOS:
        install_prefix = _cmake(session, BUILD_TYPE_RELEASE)
        command = get_path("scripts", "macos", "nox-install-for-doctest.sh")
        env = {INSTALL_PREFIX_ENV: install_prefix}
        session.run(command, external=True, env=env)
    else:
        install_prefix = install_bezier(session)
    # Use custom RC-file for matplotlib.
    env = {
        INSTALL_PREFIX_ENV: install_prefix,
        "GENERATE_IMAGES": "True",
        "MATPLOTLIBRC": "docs",
        "PYTHONPATH": get_path(),
    }
    # Run the script for generating images for docs.
    run_args = get_doctest_args(session)
    session.run(*run_args, env=env)
    make_images = get_path("docs", "make_images.py")
    session.run("python", make_images, env=env)
    # Run the functional tests with --save-plot.
    fnl_tests_glob = get_path("tests", "functional", "test_*.py")
    modules_to_run = glob.glob(fnl_tests_glob)
    # Generate images for ``curve_intersections.json`` and
    # ``triangle_intersections.json``.
    modules_to_run.extend(
        (
            get_path("tests", "functional", "make_segment_box_images.py"),
            get_path("tests", "functional", "make_triangle_locate_images.py"),
            get_path("tests", "functional", "make_curve_curve_images.py"),
            get_path(
                "tests", "functional", "make_triangle_triangle_images.py"
            ),
        )
    )
    # Make sure that the root directory is on the Python path so that
    # ``tests`` is import-able.
    env["PYTHONPATH"] = get_path()
    for filename in modules_to_run:
        session.run("python", filename, "--save-plot", env=env)


@nox.session(py=DEFAULT_INTERPRETER)
def lint(session):
    # Install all dependencies.
    local_deps = BASE_DEPS + (
        DEPS["black"],
        DEPS["cmake-format"],
        DEPS["docutils"],
        DEPS["flake8"],
        DEPS["flake8-import-order"],
        DEPS["matplotlib"],
        DEPS["Pygments"],
        DEPS["pylint"],
        DEPS["scipy"],
        DEPS["seaborn"],
        DEPS["sympy"],
    )
    session.install(*local_deps)
    # Install this package.
    install_bezier(session)
    # Run the script to check that the README and other docs are valid.
    check_path = get_path("scripts", "check_doc_templates.py")
    session.run("python", check_path)
    # Run the script to check that setup.py is valid.
    setup_file = get_path("setup.py")
    session.run(
        "python",
        setup_file,
        "check",
        "--metadata",
        "--restructuredtext",
        "--strict",
        env={"BEZIER_NO_EXTENSION": "True"},
    )
    # Run ``black --check`` over all Python files
    check_black = get_path("scripts", "black_check_all_files.py")
    session.run("python", check_black)
    # Run flake8 over the code to check import order.
    session.run(
        "flake8",
        "--import-order-style=google",
        "--application-import-names=bezier,tests",
        get_path("src", "python", "bezier"),
        get_path("tests"),
    )
    # Run Pylint over the library source.
    session.run(
        "pylint",
        "--rcfile",
        "pylintrc",
        "--max-module-lines=3035",
        "--disable=missing-type-doc",
        get_path("src", "python", "bezier"),
    )
    # Run Pylint over the tests source.
    session.run(
        "pylint",
        "--rcfile",
        "pylintrc",
        "--disable=missing-docstring",
        "--disable=protected-access",
        "--disable=too-many-public-methods",
        "--disable=import-outside-toplevel",
        "--disable=arguments-out-of-order",
        "--max-module-lines=2473",
        get_path("tests"),
    )
    # Run ``cmake-format`` for uniform formatting of ``CMakeLists.txt`` files
    session.run(
        "cmake-format",
        "--in-place",
        get_path("src", "fortran", "CMakeLists.txt"),
    )
    # (Maybe) run ``clang-format`` for uniform formatting of ``.c`` and ``.h``
    # files
    if py.path.local.sysfind("clang-format") is not None:
        filenames = glob.glob(get_path("docs", "abi", "*.c"))
        filenames.append(get_path("src", "fortran", "include", "bezier.h"))
        filenames.extend(
            glob.glob(get_path("src", "fortran", "include", "bezier", "*.h"))
        )
        session.run(
            "clang-format", "-i", "-style=file", *filenames, external=True
        )


@nox.session(py=DEFAULT_INTERPRETER)
def blacken(session):
    """Run black code formatter."""
    session.install(DEPS["black"])
    check_black = get_path("scripts", "blacken_all_files.py")
    session.run("python", check_black)


@nox.session(py=DEFAULT_INTERPRETER)
def fortran_unit(session):
    session.install(DEPS["lcov_cobertura"], DEPS["pycobertura"])
    if py.path.local.sysfind("make") is None:
        session.skip("`make` must be installed")
    if py.path.local.sysfind("gfortran") is None:
        session.skip("`gfortran` must be installed")
    if py.path.local.sysfind("lcov") is None:
        session.skip("`lcov` must be installed")
    test_dir = get_path("tests", "fortran")
    lcov_filename = os.path.join(test_dir, "coverage.info")
    session.chdir(test_dir)
    session.run("make", "unit", external=True)
    session.chdir(NOX_DIR)
    session.run(
        "lcov",
        "--capture",
        "--directory",
        test_dir,
        "--output-file",
        lcov_filename,
        external=True,
    )
    session.run(
        "python",
        get_path("scripts", "report_lcov.py"),
        "--lcov-filename",
        lcov_filename,
    )
    session.chdir(test_dir)
    session.run("make", "clean", external=True)


@nox.session(py=DEFAULT_INTERPRETER)
def validate_functional_test_cases(session):
    # Install all dependencies.
    session.install(DEPS["jsonschema"])

    session.run(
        "python", get_path("scripts", "validate_functional_test_cases.py")
    )


def _cmake_libbezier_root(session, build_type):
    """The **path** to the Nox shared directory for the build type.

    This path is dependent on build type. e.g. e.g. if ``build_type`` is
    ``Debug``, then the ``.nox/.cache/libbezier-debug`` is expected to be
    returned. This subdirectory will be created if it doesn't exist.

    If the ``session`` is actually running as part of the intended
    ``build_type``, this will ensure a full virtual environment is created
    as well.
    """
    if build_type == BUILD_TYPE_DEBUG:
        build_session_name = DEBUG_SESSION_NAME
    elif build_type == BUILD_TYPE_RELEASE:
        build_session_name = RELEASE_SESSION_NAME
    else:
        raise ValueError(f"Invalid build type {build_type!r}")

    if session._runner.name == build_session_name:
        # Force the virtual environment to be (re-)created if it doesn't
        # have a ``bin`` directory. This can happen if a build was invoked from
        # another session function.
        if not os.path.isdir(session.bin):
            reuse_value = session.virtualenv.reuse_existing
            session.virtualenv.reuse_existing = False
            session.virtualenv.create()
            session.virtualenv.reuse_existing = reuse_value

    relative_path = session.cache_dir / build_session_name
    # Convert to an absolute path.
    libbezier_root = get_path(relative_path)
    session.run(os.makedirs, libbezier_root, exist_ok=True)
    return libbezier_root


def _cmake_needed():
    """Determine if a ``cmake`` binary is needed.

    This will check if ``cmake`` is on the path so it can be used if needed.
    Installing ``cmake`` into the ``nox``-managed virtual environment can be
    forced by setting the ``NOX_INSTALL_CMAKE`` environment variable.
    """
    if "NOX_INSTALL_CMAKE" in os.environ:
        return True

    return py.path.local.sysfind("cmake") is None


def _cmake(session, build_type):
    """Build and install ``libbezier`` via ``cmake``.

    The ``session`` may be one of ``libbezier-debug`` / ``libbezier-release``
    in which case we directly build as instructed. Additionally, it may
    correspond to a session that seeks to build ``libbezier`` as a dependency,
    e.g. ``nox --session unit-3.10``.

    Returns:
        str: The install prefix that was created / re-used.
    """
    libbezier_root = _cmake_libbezier_root(session, build_type)

    cmake_external = True
    if _cmake_needed():
        session.install(DEPS["cmake"])
        cmake_external = False
    else:
        session.run_always(print, "Using pre-installed ``cmake``")
        session.run_always("cmake", "--version", external=cmake_external)

    # Prepare build and install directories.
    build_dir = os.path.join(libbezier_root, "build")
    install_prefix = os.path.join(libbezier_root, "usr")
    session.run_always(os.makedirs, build_dir, exist_ok=True)

    # Run ``cmake`` to prepare for / configure the build.
    build_args = [
        "cmake",
        "-DCMAKE_BUILD_TYPE={}".format(build_type),
        "-DCMAKE_INSTALL_PREFIX:PATH={}".format(install_prefix),
        "-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON",
    ]
    if IS_WINDOWS:
        build_args.extend(["-G", "MinGW Makefiles"])
    if os.environ.get("TARGET_NATIVE_ARCH") == "OFF":
        build_args.append("-DTARGET_NATIVE_ARCH:BOOL=OFF")

    build_args.extend(["-S", os.path.join("src", "fortran"), "-B", build_dir])
    session.run_always(*build_args, external=cmake_external)

    # Build and install.
    session.run_always(
        "cmake",
        "--build",
        build_dir,
        "--config",
        build_type,
        "--target",
        "install",
        external=cmake_external,
    )

    # Get information on how the build was configured.
    session.run_always("cmake", "-L", build_dir, external=cmake_external)

    return install_prefix


@nox.session(name=DEBUG_SESSION_NAME)
def cmake_debug(session):
    """Run a Debug build of ``libbezier`` and install (via ``cmake``)."""
    _cmake(session, BUILD_TYPE_DEBUG)


@nox.session(name=RELEASE_SESSION_NAME)
def cmake_release(session):
    """Run a Release build of ``libbezier`` and install (via ``cmake``)."""
    _cmake(session, BUILD_TYPE_RELEASE)


@nox.session(py=False)
def clean(session):
    """Clean up build files.

    Cleans up all artifacts that might get created during
    other ``nox`` sessions.

    There is no need for the session to create a ``virtualenv``
    here (we are just pretending to be ``make``).
    """
    clean_dirs = (
        get_path(".cache"),
        get_path(".coverage"),
        get_path(".pytest_cache"),
        get_path("__pycache__"),
        get_path("build"),
        get_path("dist"),
        get_path("docs", "__pycache__"),
        get_path("docs", "build"),
        get_path("scripts", "macos", "__pycache__"),
        get_path("scripts", "macos", "dist_wheels"),
        get_path("scripts", "macos", "fixed_wheels"),
        get_path("scripts", "macos", "test-venv"),
        get_path("scripts", "manylinux", "fixed_wheels"),
        get_path("src", "python", "bezier.egg-info"),
        get_path("src", "python", "bezier", "__pycache__"),
        get_path("src", "python", "bezier", "extra-dll"),
        get_path("tests", "__pycache__"),
        get_path("tests", "functional", "__pycache__"),
        get_path("tests", "unit", "__pycache__"),
        get_path("tests", "unit", "hazmat", "__pycache__"),
        get_path("wheelhouse"),
    )
    clean_globs = (
        get_path(".coverage"),
        get_path("*.mod"),
        get_path("*.pyc"),
        get_path("docs", "abi", "example"),
        get_path("src", "python", "bezier", "*.pyc"),
        get_path("src", "python", "bezier", "*.pyd"),
        get_path("src", "python", "bezier", "*.so"),
        get_path("src", "fortran", "*.o"),
        get_path("tests", "*.pyc"),
        get_path("tests", "functional", "*.pyc"),
        get_path("tests", "unit", "*.pyc"),
    )
    for dir_path in clean_dirs:
        session.run(shutil.rmtree, dir_path, ignore_errors=True)
    for glob_path in clean_globs:
        for filename in glob.glob(glob_path):
            session.run(os.remove, filename)
