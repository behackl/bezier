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

import unittest
import unittest.mock

import numpy as np
import pytest
import six

try:
    from bezier import _HAS_SURFACE_SPEEDUP as HAS_SURFACE_SPEEDUP
except ImportError:  # pragma: NO COVER
    HAS_SURFACE_SPEEDUP = False
from tests.unit import utils


UNIT_TRIANGLE = np.asfortranarray([
    [0.0, 0.0],
    [1.0, 0.0],
    [0.0, 1.0],
])
FLOAT64 = np.float64  # pylint: disable=no-member
# pylint: disable=invalid-name,no-member
slow = pytest.mark.skipif(
    pytest.config.getoption('--ignore-slow') and not HAS_SURFACE_SPEEDUP,
    reason='--ignore-slow ignores the slow tests',
)
# pylint: enable=invalid-name,no-member


class Test_polynomial_sign(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(poly_surface, degree):
        from bezier import _surface_helpers

        return _surface_helpers.polynomial_sign(poly_surface, degree)

    def test_positive(self):
        bernstein = np.asfortranarray(
            [[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]])
        sign = self._call_function_under_test(bernstein, 2)
        self.assertEqual(sign, 1)

    def test_negative(self):
        bernstein = np.asfortranarray([[-1.0], [-2.0], [-1.0]])
        sign = self._call_function_under_test(bernstein, 1)
        self.assertEqual(sign, -1)

    def test_zero(self):
        bernstein = np.zeros((10, 1), order='F')
        sign = self._call_function_under_test(bernstein, 3)
        self.assertEqual(sign, 0)

    def test_mixed(self):
        bernstein = np.asfortranarray([[-1.0], [1.0], [-1.0]])
        sign = self._call_function_under_test(bernstein, 1)
        self.assertEqual(sign, 0)

    def test_max_iterations(self):
        bernstein = np.asfortranarray([[1.0], [2.0], [3.0]])
        subs = 'bezier._surface_helpers._MAX_POLY_SUBDIVISIONS'
        with unittest.mock.patch(subs, new=1):
            sign = self._call_function_under_test(bernstein, 1)
            self.assertEqual(sign, 1)

    def test_no_conclusion(self):
        bernstein = np.asfortranarray([[-1.0], [1.0], [2.0]])
        subs = 'bezier._surface_helpers._MAX_POLY_SUBDIVISIONS'
        with unittest.mock.patch(subs, new=0):
            with self.assertRaises(ValueError):
                self._call_function_under_test(bernstein, 1)

    def test_conclusion_from_corner_node(self):
        # NOTE: This comes from the surface defined by
        #          [0.0   0.0  ]
        #          [0.5   0.5  ]
        #          [1.0   0.625]
        #          [0.0   0.5  ]
        #          [0.5   0.5  ]
        #          [0.25  1.0  ]
        bernstein = np.asfortranarray([
            [1.0], [0.5], [0.0], [0.75], [0.4375], [1.0]])
        sign = self._call_function_under_test(bernstein, 2)
        self.assertEqual(sign, 0)


class Test_two_by_two_det(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(mat):
        from bezier import _surface_helpers

        return _surface_helpers.two_by_two_det(mat)

    def test_integers(self):
        mat = np.asfortranarray([
            [1.0, 2.0],
            [3.0, 4.0],
        ])
        self.assertEqual(self._call_function_under_test(mat), -2.0)

    def test_better_than_numpy(self):
        mat = np.asfortranarray([
            [-24.0, 3.0],
            [-27.0, 0.0],
        ]) / 16.0
        actual_det = self._call_function_under_test(mat)
        self.assertEqual(actual_det, 81.0 / 256.0)

        np_det = np.linalg.det(mat)
        self.assertNotEqual(actual_det, np_det)
        self.assertLess(abs(actual_det - np_det), 1e-16)


class Test_quadratic_jacobian_polynomial(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes):
        from bezier import _surface_helpers

        return _surface_helpers.quadratic_jacobian_polynomial(nodes)

    def test_it(self):
        # B(L1, L2, L3) = [L1^2 + L2^2, L2^2 + L3^2]
        nodes = np.asfortranarray([
            [1.0, 0.0],
            [0.0, 0.0],
            [1.0, 1.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 1.0],
        ])
        bernstein = self._call_function_under_test(nodes)
        expected = np.asfortranarray([
            [0.0], [2.0], [0.0], [-2.0], [2.0], [0.0]])
        self.assertEqual(bernstein, expected)

    def test_against_det(self):
        from bezier import _surface_helpers

        # B(L1, L2, L3) = [s (t + 2), s^2 + 4 t]
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 1.0],
            [0.0, 2.0],
            [1.5, 2.0],
            [0.0, 4.0],
        ])

        st_vals = np.asfortranarray([
            [0.0, 0.0],
            [0.5, 0.0],
            [1.0, 0.0],
            [0.0, 0.5],
            [0.5, 0.5],
            [0.0, 1.0],
        ])
        as_det = _surface_helpers.jacobian_det(nodes, 2, st_vals)
        as_det = as_det.reshape((6, 1), order='F')
        # B_s = [t + 2, 2*s]
        # B_t = [s, 4]
        # det(DB) = -2 (s^2 - 2t - 4)
        bernstein = self._call_function_under_test(nodes)
        evaluated_bernstein = _surface_helpers.evaluate_cartesian_multi(
            bernstein, 2, st_vals, 1)
        self.assertEqual(evaluated_bernstein, as_det)


class Test_cubic_jacobian_polynomial(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes):
        from bezier import _surface_helpers

        return _surface_helpers.cubic_jacobian_polynomial(nodes)

    def test_it(self):
        # B(L1, L2, L3) = [L1^3 + L2^3, L2^3 + L3^3]
        nodes = np.asfortranarray([
            [1.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [1.0, 1.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0, 1.0],
        ])
        bernstein = self._call_function_under_test(nodes)
        shape = (15, 1)
        self.assertEqual(bernstein.shape, shape)
        expected = np.zeros(shape, order='F')
        expected[2, 0] = 1.5
        expected[9, 0] = -1.5
        expected[11, 0] = 1.5
        self.assertEqual(bernstein, expected)


class Test__de_casteljau_one_round(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, lambda1, lambda2, lambda3):
        from bezier import _surface_helpers

        return _surface_helpers._de_casteljau_one_round(
            nodes, degree, lambda1, lambda2, lambda3)

    def test_linear(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ])
        s_val, t_val = 0.5, 0.375
        expected = np.asfortranarray([
            [s_val, t_val],
        ])

        result = self._call_function_under_test(
            nodes, 1, 1.0 - s_val - t_val, s_val, t_val)
        self.assertEqual(result, expected)

    def test_quadratic(self):
        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        nodes = utils.get_random_nodes(
            shape=(6, 2), seed=97764, num_bits=8)

        p200, p110, p020, p101, p011, p002 = nodes
        s_val = 0.25
        t_val = 0.125

        q100 = (1.0 - s_val - t_val) * p200 + s_val * p110 + t_val * p101
        q010 = (1.0 - s_val - t_val) * p110 + s_val * p020 + t_val * p011
        q001 = (1.0 - s_val - t_val) * p101 + s_val * p011 + t_val * p002

        expected = np.asfortranarray(np.vstack([q100, q010, q001]))
        result = self._call_function_under_test(
            nodes, 2, 1.0 - s_val - t_val, s_val, t_val)
        self.assertEqual(result, expected)

    def test_cubic(self):
        from bezier import _helpers

        nodes = np.asfortranarray([
            [0.0, 0.0],
            [3.25, 1.5],
            [6.5, 1.5],
            [10.0, 0.0],
            [1.5, 3.25],
            [5.0, 5.0],
            [10.0, 5.25],
            [1.5, 6.5],
            [5.25, 10.0],
            [0.0, 10.0],
        ])

        s_val = 0.25
        t_val = 0.375
        lambda1 = 1.0 - s_val - t_val
        transform = np.asfortranarray([
            [lambda1, s_val, 0., 0., t_val, 0., 0., 0., 0., 0.],
            [0., lambda1, s_val, 0., 0., t_val, 0., 0., 0., 0.],
            [0., 0., lambda1, s_val, 0., 0., t_val, 0., 0., 0.],
            [0., 0., 0., 0., lambda1, s_val, 0., t_val, 0., 0.],
            [0., 0., 0., 0., 0., lambda1, s_val, 0., t_val, 0.],
            [0., 0., 0., 0., 0., 0., 0., lambda1, s_val, t_val],
        ])
        expected = _helpers.matrix_product(transform, nodes)
        result = self._call_function_under_test(
            nodes, 3, lambda1, s_val, t_val)
        self.assertEqual(result, expected)


@utils.needs_surface_speedup
class Test_speedup_de_casteljau_one_round(Test__de_casteljau_one_round):

    @staticmethod
    def _call_function_under_test(nodes, degree, lambda1, lambda2, lambda3):
        from bezier import _surface_speedup

        return _surface_speedup.de_casteljau_one_round(
            nodes, degree, lambda1, lambda2, lambda3)


class Test_make_transform(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(degree, weights_a, weights_b, weights_c):
        from bezier import _surface_helpers

        return _surface_helpers.make_transform(
            degree, weights_a, weights_b, weights_c)

    def _helper(self, degree, weights, expected0, expected1, expected2):
        result = self._call_function_under_test(
            degree, weights[0, :], weights[1, :], weights[2, :])

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], expected0)
        self.assertEqual(result[1], expected1)
        self.assertEqual(result[2], expected2)

    def test_linear(self):
        weights = np.asfortranarray([
            [1.0, 0.0, 0.0],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
        ])
        expected0 = np.asfortranarray(weights[[0], :])
        expected1 = np.asfortranarray(weights[[1], :])
        expected2 = np.asfortranarray(weights[[2], :])
        self._helper(1, weights, expected0, expected1, expected2)

    def test_quadratic(self):
        weights = np.asfortranarray([
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ])
        expected0 = np.asfortranarray([
            [0.0, 0.5, 0.0, 0.5, 0.0, 0.0],
            [0.0, 0.0, 0.5, 0.0, 0.5, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.5, 0.5],
        ])
        expected1 = np.asfortranarray([
            [0.5, 0.0, 0.0, 0.5, 0.0, 0.0],
            [0.0, 0.5, 0.0, 0.0, 0.5, 0.0],
            [0.0, 0.0, 0.0, 0.5, 0.0, 0.5],
        ])
        expected2 = np.asfortranarray([
            [0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.5, 0.5, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.5, 0.5, 0.0],
        ])
        self._helper(2, weights, expected0, expected1, expected2)


class Test_reduced_to_matrix(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(shape, degree, vals_by_weight):
        from bezier import _surface_helpers

        return _surface_helpers.reduced_to_matrix(
            shape, degree, vals_by_weight)

    def test_it(self):
        shape = (6, 2)
        degree = 2

        expected = np.asfortranarray([
            [1.0, 0.0],
            [-1.0, 1.0],
            [0.0, 1.0],
            [0.0, -1.0],
            [-1.0, -1.0],
            [2.0, 0.0],
        ])
        vals_by_weight = {
            (0, 0): expected[[0], :],
            (0, 1): expected[[1], :],
            (1, 1): expected[[2], :],
            (0, 2): expected[[3], :],
            (1, 2): expected[[4], :],
            (2, 2): expected[[5], :],
        }

        result = self._call_function_under_test(shape, degree, vals_by_weight)
        self.assertEqual(result, expected)


class Test__specialize_surface(utils.NumPyTestCase):

    WEIGHTS0 = np.asfortranarray([1.0, 0.0, 0.0])
    WEIGHTS1 = np.asfortranarray([0.5, 0.5, 0.0])
    WEIGHTS2 = np.asfortranarray([0.0, 1.0, 0.0])
    WEIGHTS3 = np.asfortranarray([0.5, 0.0, 0.5])
    WEIGHTS4 = np.asfortranarray([0.0, 0.5, 0.5])
    WEIGHTS5 = np.asfortranarray([0.0, 0.0, 1.0])

    @staticmethod
    def _call_function_under_test(
            nodes, degree, weights_a, weights_b, weights_c):
        from bezier import _surface_helpers

        return _surface_helpers._specialize_surface(
            nodes, degree, weights_a, weights_b, weights_c)

    def _helper(self, degree, expected_a, expected_b, expected_c, expected_d):
        from bezier import _helpers

        num_nodes = ((degree + 1) * (degree + 2)) // 2
        id_mat = _helpers.eye(num_nodes)

        computed_a = self._call_function_under_test(
            id_mat, degree,
            self.WEIGHTS0, self.WEIGHTS1, self.WEIGHTS3)
        computed_b = self._call_function_under_test(
            id_mat, degree,
            self.WEIGHTS4, self.WEIGHTS3, self.WEIGHTS1)
        computed_c = self._call_function_under_test(
            id_mat, degree,
            self.WEIGHTS1, self.WEIGHTS2, self.WEIGHTS4)
        computed_d = self._call_function_under_test(
            id_mat, degree,
            self.WEIGHTS3, self.WEIGHTS4, self.WEIGHTS5)

        self.assertEqual(computed_a, expected_a)
        self.assertEqual(computed_b, expected_b)
        self.assertEqual(computed_c, expected_c)
        self.assertEqual(computed_d, expected_d)

    def test_known_linear(self):
        from bezier import _surface_helpers

        self._helper(
            1, _surface_helpers.LINEAR_SUBDIVIDE_A,
            _surface_helpers.LINEAR_SUBDIVIDE_B,
            _surface_helpers.LINEAR_SUBDIVIDE_C,
            _surface_helpers.LINEAR_SUBDIVIDE_D)

    def test_known_quadratic(self):
        from bezier import _surface_helpers

        self._helper(
            2, _surface_helpers.QUADRATIC_SUBDIVIDE_A,
            _surface_helpers.QUADRATIC_SUBDIVIDE_B,
            _surface_helpers.QUADRATIC_SUBDIVIDE_C,
            _surface_helpers.QUADRATIC_SUBDIVIDE_D)

    def test_known_cubic(self):
        from bezier import _surface_helpers

        self._helper(
            3, _surface_helpers.CUBIC_SUBDIVIDE_A,
            _surface_helpers.CUBIC_SUBDIVIDE_B,
            _surface_helpers.CUBIC_SUBDIVIDE_C,
            _surface_helpers.CUBIC_SUBDIVIDE_D)

    def test_known_quartic(self):
        from bezier import _surface_helpers

        self._helper(
            4, _surface_helpers.QUARTIC_SUBDIVIDE_A,
            _surface_helpers.QUARTIC_SUBDIVIDE_B,
            _surface_helpers.QUARTIC_SUBDIVIDE_C,
            _surface_helpers.QUARTIC_SUBDIVIDE_D)


@utils.needs_surface_speedup
class Test_speedup_specialize_surface(Test__specialize_surface):

    @staticmethod
    def _call_function_under_test(
            nodes, degree, weights_a, weights_b, weights_c):
        from bezier import _surface_speedup

        return _surface_speedup.specialize_surface(
            nodes, degree, weights_a, weights_b, weights_c)


class Test__subdivide_nodes(utils.NumPyTestCase):

    REF_TRIANGLE = utils.ref_triangle_uniform_nodes(5)

    @staticmethod
    def _call_function_under_test(nodes, degree):
        from bezier import _surface_helpers

        return _surface_helpers._subdivide_nodes(nodes, degree)

    def _helper(self, nodes, degree, expected_a,
                expected_b, expected_c, expected_d):
        nodes_a, nodes_b, nodes_c, nodes_d = self._call_function_under_test(
            nodes, degree)

        self.assertEqual(nodes_a, expected_a)
        self.assertEqual(nodes_b, expected_b)
        self.assertEqual(nodes_c, expected_c)
        self.assertEqual(nodes_d, expected_d)

    def _points_check(self, nodes, degree):
        from bezier import _surface_helpers

        _, dimension = nodes.shape
        sub_surfaces = self._call_function_under_test(
            nodes, degree)

        ref_triangle = self.REF_TRIANGLE
        quarter_a = 0.5 * ref_triangle
        quarters = [
            quarter_a,
            np.asfortranarray([0.5, 0.5]) - quarter_a,  # B
            quarter_a + np.asfortranarray([0.5, 0.0]),  # C
            quarter_a + np.asfortranarray([0.0, 0.5]),  # D
        ]

        for sub_surface, quarter in zip(sub_surfaces, quarters):
            # Make sure sub_surface(ref_triangle) == surface(quarter)
            main_vals = _surface_helpers.evaluate_cartesian_multi(
                nodes, degree, quarter, dimension)
            sub_vals = _surface_helpers.evaluate_cartesian_multi(
                sub_surface, degree, ref_triangle, dimension)
            self.assertEqual(main_vals, sub_vals)

    def test_linear(self):
        expected_a = np.asfortranarray([
            [0.0, 0.0],
            [0.5, 0.0],
            [0.0, 0.5],
        ])
        expected_b = np.asfortranarray([
            [0.5, 0.5],
            [0.0, 0.5],
            [0.5, 0.0],
        ])
        expected_c = np.asfortranarray([
            [0.5, 0.0],
            [1.0, 0.0],
            [0.5, 0.5],
        ])
        expected_d = np.asfortranarray([
            [0.0, 0.5],
            [0.5, 0.5],
            [0.0, 1.0],
        ])
        self._helper(
            UNIT_TRIANGLE, 1,
            expected_a, expected_b, expected_c, expected_d)

    @slow
    def test_line_check_evaluate(self):
        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        nodes = utils.get_random_nodes(
            shape=(3, 2), seed=123987, num_bits=8)
        self._points_check(nodes, 1)

    def test_quadratic(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [0.5, 0.25],
            [1.0, 0.0],
            [0.5, 0.75],
            [0.0, 1.0],
            [0.0, 0.5],
        ])
        expected_a = np.asfortranarray([
            [0.0, 0.0],
            [0.25, 0.125],
            [0.5, 0.125],
            [0.25, 0.375],
            [0.25, 0.5],
            [0.25, 0.5],
        ])
        expected_b = np.asfortranarray([
            [0.25, 0.625],
            [0.25, 0.625],
            [0.25, 0.5],
            [0.5, 0.5],
            [0.25, 0.5],
            [0.5, 0.125],
        ])
        expected_c = np.asfortranarray([
            [0.5, 0.125],
            [0.75, 0.125],
            [1.0, 0.0],
            [0.5, 0.5],
            [0.5, 0.5],
            [0.25, 0.625],
        ])
        expected_d = np.asfortranarray([
            [0.25, 0.5],
            [0.25, 0.625],
            [0.25, 0.625],
            [0.25, 0.625],
            [0.0, 0.75],
            [0.0, 0.5],
        ])
        self._helper(
            nodes, 2, expected_a, expected_b, expected_c, expected_d)

    @slow
    def test_quadratic_check_evaluate(self):
        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        nodes = utils.get_random_nodes(
            shape=(6, 2), seed=45001, num_bits=8)
        self._points_check(nodes, 2)

    def test_cubic(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [3.25, 1.5],
            [6.5, 1.5],
            [10.0, 0.0],
            [1.5, 3.25],
            [5.0, 5.0],
            [10.0, 5.25],
            [1.5, 6.5],
            [5.25, 10.0],
            [0.0, 10.0],
        ])
        expected_a = np.asfortranarray([
            [0.0, 0.0],
            [1.625, 0.75],
            [3.25, 1.125],
            [4.90625, 1.125],
            [0.75, 1.625],
            [2.4375, 2.4375],
            [4.3125, 2.875],
            [1.125, 3.25],
            [2.875, 4.3125],
            [1.125, 4.90625],
        ])
        expected_b = np.asfortranarray([
            [6.96875, 6.96875],
            [4.8125, 6.65625],
            [2.875, 5.96875],
            [1.125, 4.90625],
            [6.65625, 4.8125],
            [4.75, 4.75],
            [2.875, 4.3125],
            [5.96875, 2.875],
            [4.3125, 2.875],
            [4.90625, 1.125],
        ])
        expected_c = np.asfortranarray([
            [4.90625, 1.125],
            [6.5625, 1.125],
            [8.25, 0.75],
            [10.0, 0.0],
            [5.96875, 2.875],
            [7.875, 2.9375],
            [10.0, 2.625],
            [6.65625, 4.8125],
            [8.8125, 5.125],
            [6.96875, 6.96875],
        ])
        expected_d = np.asfortranarray([
            [1.125, 4.90625],
            [2.875, 5.96875],
            [4.8125, 6.65625],
            [6.96875, 6.96875],
            [1.125, 6.5625],
            [2.9375, 7.875],
            [5.125, 8.8125],
            [0.75, 8.25],
            [2.625, 10.0],
            [0.0, 10.0],
        ])
        self._helper(
            nodes, 3, expected_a, expected_b, expected_c, expected_d)

    @slow
    def test_cubic_check_evaluate(self):
        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        nodes = utils.get_random_nodes(
            shape=(10, 2), seed=346323, num_bits=8)
        self._points_check(nodes, 3)

    @slow
    def test_quartic_check_evaluate(self):
        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        nodes = utils.get_random_nodes(
            shape=(15, 2), seed=741002, num_bits=8)
        self._points_check(nodes, 4)

    @slow
    def test_on_the_fly(self):
        # Test for a degree where the subdivision is done on the fly
        # rather than via a stored matrix.
        nodes = utils.get_random_nodes(
            shape=(21, 2), seed=446, num_bits=8)
        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        self._points_check(nodes, 5)


@utils.needs_surface_speedup
class Test_speedup_subdivide_nodes(Test__subdivide_nodes):

    @staticmethod
    def _call_function_under_test(nodes, degree):
        from bezier import _surface_speedup

        return _surface_speedup.subdivide_nodes(nodes, degree)


class Test_jacobian_s(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, dimension):
        from bezier import _surface_helpers

        return _surface_helpers.jacobian_s(nodes, degree, dimension)

    def test_linear(self):
        nodes = np.asfortranarray([[0.0], [1.0], [np.nan]])
        result = self._call_function_under_test(nodes, 1, 1)
        expected = np.asfortranarray([[1.0]])
        self.assertEqual(result, expected)

    def test_quadratic(self):
        nodes = np.asfortranarray([
            [0.0, 1.0],
            [1.0, 11.0],
            [5.0, 7.0],
            [4.0, -2.0],
            [-1.0, 6.0],
            [np.nan, np.nan],
        ])
        result = self._call_function_under_test(nodes, 2, 2)
        expected = 2.0 * np.asfortranarray([
            [1.0, 10.0],
            [4.0, -4.0],
            [-5.0, 8.0],
        ])
        self.assertEqual(result, expected)

    def test_cubic(self):
        nodes = np.arange(10, dtype=FLOAT64)[:, np.newaxis]**2
        result = self._call_function_under_test(nodes, 3, 1)
        expected = 3 * np.asfortranarray([
            [1], [3], [5], [9], [11], [15]], dtype=FLOAT64)
        self.assertEqual(result, expected)

    def test_quartic(self):
        nodes = np.arange(15, dtype=FLOAT64)[:, np.newaxis]**2
        result = self._call_function_under_test(nodes, 4, 1)
        expected = 4 * np.asfortranarray([
            [1], [3], [5], [7], [11], [13],
            [15], [19], [21], [25]], dtype=FLOAT64)
        self.assertEqual(result, expected)


class Test_jacobian_t(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, dimension):
        from bezier import _surface_helpers

        return _surface_helpers.jacobian_t(nodes, degree, dimension)

    def test_linear(self):
        nodes = np.asfortranarray([[0.0], [np.nan], [1.0]])
        result = self._call_function_under_test(nodes, 1, 1)
        expected = np.asfortranarray([[1.0]])
        self.assertEqual(result, expected)

    def test_quadratic(self):
        nodes = np.asfortranarray([
            [4.0, -2.0],
            [0.0, 1.0],
            [np.nan, np.nan],
            [5.0, 7.0],
            [-1.0, 6.0],
            [1.0, 12.0],
        ])
        result = self._call_function_under_test(nodes, 2, 2)
        expected = 2.0 * np.asfortranarray([
            [1.0, 9.0],
            [-1.0, 5.0],
            [-4.0, 5.0],
        ])
        self.assertEqual(result, expected)

    def test_cubic(self):
        nodes = np.arange(10, dtype=FLOAT64)[:, np.newaxis]**2
        result = self._call_function_under_test(nodes, 3, 1)
        expected = 3 * np.asfortranarray(
            [[16], [24], [32], [33], [39], [32]], dtype=FLOAT64)
        self.assertEqual(result, expected)

    def test_quartic(self):
        nodes = np.arange(15, dtype=FLOAT64)[:, np.newaxis]**2
        result = self._call_function_under_test(nodes, 4, 1)
        expected = 4 * np.asfortranarray([
            [25], [35], [45], [55], [56],
            [64], [72], [63], [69], [52],
        ], dtype=FLOAT64)
        self.assertEqual(result, expected)


class Test__jacobian_both(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, dimension):
        from bezier import _surface_helpers

        return _surface_helpers._jacobian_both(nodes, degree, dimension)

    def test_linear(self):
        # B(s, t) = -2s + 2t + 3
        nodes = np.asfortranarray([
            [3.0],
            [1.0],
            [5.0],
        ])
        result = self._call_function_under_test(nodes, 1, 1)

        # B_s = -2
        # B_t = 2
        expected = np.asfortranarray([
            [-2.0, 2.0],
        ])
        self.assertEqual(result, expected)

    def test_quadratic(self):
        # B(s, t) = [
        #     4 s t - 2 s + 5 t^2 - 6 t + 3,
        #     -s (s - 2 t),
        #     8 s^2 - 10 s t - 2 s - 13 t^2 + 12 t + 1,
        # ]
        #
        nodes = np.asfortranarray([
            [3.0, 0.0, 1.0],
            [2.0, 0.0, 0.0],
            [1.0, -1.0, 7.0],
            [0.0, 0.0, 7.0],
            [1.0, 1.0, 1.0],
            [2.0, 0.0, 0.0],
        ])
        result = self._call_function_under_test(nodes, 2, 3)

        # B_s = [
        #     4 t - 2,
        #     -2 s + 2 t,
        #     16 s - 10 t - 2,
        # ]
        # B_t = [
        #     4 s + 10 t - 6,
        #     2 s,
        #    -10 s - 26 t + 12,
        # ]
        expected = np.asfortranarray([
            [-2.0, 0.0, -2.0, -6.0, 0.0, 12.0],
            [-2.0, -2.0, 14.0, -2.0, 2.0, 2.0],
            [2.0, 2.0, -12.0, 4.0, 0.0, -14.0],
        ])
        self.assertEqual(result, expected)

    def test_cubic(self):
        # B(s, t) = [
        #     -2s^3 + 9s^2t + 12st^2 - 12st + 3s - 2t^3 + 6t,
        #     (-10s^3 - 30s^2t + 30s^2 - 36st^2 + 42st -
        #          18s - 15t^3 + 30t^2 - 18t + 7),
        # ]
        nodes = np.asfortranarray([
            [0.0, 7.0],
            [1.0, 1.0],
            [2.0, 5.0],
            [1.0, 9.0],
            [2.0, 1.0],
            [1.0, 2.0],
            [3.0, 3.0],
            [4.0, 5.0],
            [5.0, 1.0],
            [4.0, 4.0],
        ])
        result = self._call_function_under_test(nodes, 3, 2)

        # B_s = [
        #     -6s^2 + 18st + 12t^2 - 12t + 3,
        #     -30s^2 - 60st + 60s - 36t^2 + 42t - 18,
        # ]
        # B_t = [
        #     9s^2 + 24st - 12s - 6t^2 + 6,
        #     -30s^2 - 72st + 42s - 45t^2 + 60t - 18,
        # ]
        expected = np.asfortranarray([
            [3.0, -18.0, 6.0, -18.0],
            [3.0, 12.0, 0.0, 3.0],
            [-3.0, 12.0, 3.0, -6.0],
            [-3.0, 3.0, 6.0, 12.0],
            [6.0, 3.0, 12.0, -3.0],
            [3.0, -12.0, 0.0, -3.0],
        ])
        self.assertEqual(result, expected)


@utils.needs_surface_speedup
class Test_speedup_jacobian_both(Test__jacobian_both):

    @staticmethod
    def _call_function_under_test(nodes, degree, dimension):
        from bezier import _surface_speedup

        return _surface_speedup.jacobian_both(nodes, degree, dimension)


class Test__jacobian_det(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, st_vals):
        from bezier import _surface_helpers

        return _surface_helpers._jacobian_det(nodes, degree, st_vals)

    def test_linear(self):
        import bezier

        nodes = np.asfortranarray([
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 2.0],
        ])
        degree = 1
        surface = bezier.Surface(nodes, degree=degree, _copy=False)
        self.assertTrue(surface.is_valid)
        st_vals = np.asfortranarray(np.random.random((13, 2)))
        result = self._call_function_under_test(nodes, degree, st_vals)
        expected = 2.0 * np.ones(13, order='F')
        self.assertEqual(result, expected)

    def test_nonlinear(self):
        import bezier

        nodes = np.asfortranarray([
            [0.0, 0.0],
            [0.5, 0.0],
            [1.0, 0.0],
            [0.0, 0.5],
            [1.0, 1.0],
            [0.0, 1.0],
        ])
        degree = 2
        surface = bezier.Surface(nodes, degree=degree, _copy=False)
        self.assertTrue(surface.is_valid)
        # B(s, t) = [s(t + 1), t(s + 1)]
        st_vals = np.asfortranarray([
            [0.125, 0.125],
            [0.5, 0.375],
            [0.25, 0.75],
            [1.0, 0.0],
        ])
        result = self._call_function_under_test(nodes, degree, st_vals)
        # det(DB) = s + t + 1
        expected = np.asfortranarray([1.25, 1.875, 2.0, 2.0])
        self.assertEqual(result, expected)


@utils.needs_surface_speedup
class Test_speedup_jacobian_det(Test__jacobian_det):

    @staticmethod
    def _call_function_under_test(nodes, degree, st_vals):
        from bezier import _surface_speedup

        return _surface_speedup.jacobian_det(nodes, degree, st_vals)


class Test_classify_intersection(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection):
        from bezier import _surface_helpers

        return _surface_helpers.classify_intersection(intersection)

    def test_simple(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [0.0, 0.0],
            [1.0, 1.0],
        ]))
        first._edge_index = 2
        second = bezier.Curve.from_nodes(np.asfortranarray([
            [0.25, 0.0],
            [0.75, 1.0],
        ]))
        second._edge_index = 0
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=2, index_second=0)
        result = self._call_function_under_test(intersection)
        self.assertIs(result, get_enum('SECOND'))

        # Swap and classify.
        intersection = make_intersect(
            second, 0.5, first, 0.5,
            index_first=0, index_second=2)
        result = self._call_function_under_test(intersection)
        self.assertIs(result, get_enum('FIRST'))

    def test_corner_end(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [0.0, 0.0],
            [1.0, 1.0],
        ]))
        first._edge_index = 2
        second = bezier.Curve.from_nodes(np.asfortranarray([
            [1.0, 0.0],
            [1.0, 2.0],
        ]))
        second._edge_index = 2
        intersection = make_intersect(
            first, 1.0, second, 0.5,
            index_first=2, index_second=2)
        with self.assertRaises(ValueError):
            self._call_function_under_test(intersection)

    def test_corner_start(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [1.0, 1.0],
            [0.0, 0.0],
        ]))
        first._edge_index = 1
        first._previous_edge = unittest.mock.Mock(
            _edge_index=0, spec=['_edge_index', '_nodes'])
        second = bezier.Curve.from_nodes(np.asfortranarray([
            [1.0, 0.0],
            [1.0, 2.0],
        ]))
        second._edge_index = 2
        intersection = make_intersect(
            first, 0.0, second, 0.5,
            index_first=1, index_second=2,
        )
        result = self._call_function_under_test(intersection)
        self.assertIs(result, get_enum('FIRST'))

    def test_tangent(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [0.0, 0.0],
            [1.5, 1.0],
            [3.0, 0.0],
        ]))
        first._edge_index = 0
        second = bezier.Curve.from_nodes(np.asfortranarray([
            [1.0, 0.0],
            [1.5, 1.0],
            [2.0, 0.0],
        ]))
        second._edge_index = 1
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=0, index_second=1,
        )
        result = self._call_function_under_test(intersection)
        self.assertIs(result, get_enum('TANGENT_FIRST'))

    def test_ignored_corner(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        first, _, _ = surface1.edges
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [0.0, 0.0],
            [-1.0, 0.0],
            [0.0, -1.0],
        ]))
        second, _, _ = surface2.edges

        intersection = make_intersect(
            first, 0.0, second, 0.0,
            index_first=0, index_second=0,
        )
        result = self._call_function_under_test(intersection)
        self.assertIs(result, get_enum('IGNORED_CORNER'))


class Test_classify_tangent_intersection(unittest.TestCase):

    QUADRATIC1 = np.asfortranarray([
        [1.0, 0.0],
        [1.5, 1.0],
        [2.0, 0.0],
    ])
    QUADRATIC2 = np.asfortranarray([
        [0.0, 0.0],
        [1.5, 1.0],
        [3.0, 0.0],
    ])
    QUADRATIC3 = np.asfortranarray([
        [1.0, 1.0],
        [1.5, 0.0],
        [2.0, 1.0],
    ])

    @staticmethod
    def _call_function_under_test(intersection, tangent1, tangent2):
        from bezier import _surface_helpers

        return _surface_helpers.classify_tangent_intersection(
            intersection, tangent1, tangent2)

    def _call_helper(self, intersection):
        from bezier import _curve_helpers

        tangent1 = _curve_helpers.evaluate_hodograph(
            intersection.s, intersection.first._nodes)
        tangent2 = _curve_helpers.evaluate_hodograph(
            intersection.t, intersection.second._nodes)

        return self._call_function_under_test(
            intersection, tangent1, tangent2)

    def test_first_curvature(self):
        import bezier

        first = bezier.Curve(self.QUADRATIC1[::-1, :], 2)
        first._edge_index = 1
        second = bezier.Curve(self.QUADRATIC2[::-1, :], 2)
        second._edge_index = 1
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=1, index_second=1)

        result = self._call_helper(intersection)
        self.assertIs(result, get_enum('TANGENT_FIRST'))

    def test_second_curvature(self):
        import bezier

        first = bezier.Curve(self.QUADRATIC1, 2)
        first._edge_index = 1
        second = bezier.Curve(self.QUADRATIC2, 2)
        second._edge_index = 0
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=1, index_second=0)

        result = self._call_helper(intersection)
        self.assertIs(result, get_enum('TANGENT_SECOND'))

    def test_same_direction_same_curvature(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [1.0, 0.25],
            [-0.5, -0.25],
            [0.0, 0.25],
        ]))
        first._edge_index = 0
        second = bezier.Curve.from_nodes(np.asfortranarray([
            [0.75, 0.25],
            [-0.25, -0.25],
            [-0.25, 0.25],
        ]))
        second._edge_index = 0
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=0, index_second=0)
        with self.assertRaises(NotImplementedError):
            self._call_helper(intersection)

    def test_opposed_same_curvature(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [0.0, 0.25],
            [-0.5, -0.25],
            [1.0, 0.25],
        ]))
        first._edge_index = 1
        second = bezier.Curve.from_nodes(np.asfortranarray([
            [0.75, 0.25],
            [-0.25, -0.25],
            [-0.25, 0.25],
        ]))
        second._edge_index = 2
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=1, index_second=2)
        with self.assertRaises(NotImplementedError):
            self._call_helper(intersection)

    def test_opposed_same_sign_curvature_no_overlap(self):
        import bezier

        first = bezier.Curve(self.QUADRATIC1[::-1, :], 2)
        first._edge_index = 2
        second = bezier.Curve(self.QUADRATIC3, 2)
        second._edge_index = 1
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=2, index_second=1)

        result = self._call_helper(intersection)
        self.assertIs(result, get_enum('OPPOSED'))

    def test_opposed_same_sign_curvature_with_overlap(self):
        import bezier

        first = bezier.Curve(self.QUADRATIC1, 2)
        first._edge_index = 1
        second = bezier.Curve(self.QUADRATIC3[::-1, :], 2)
        second._edge_index = 1
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=1, index_second=1)

        with self.assertRaises(NotImplementedError):
            self._call_helper(intersection)

    def test_opposed_opp_sign_curvature_no_overlap(self):
        import bezier

        first = bezier.Curve(self.QUADRATIC1[::-1, :], 2)
        first._edge_index = 1
        second = bezier.Curve(self.QUADRATIC2, 2)
        second._edge_index = 2
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=1, index_second=2)

        result = self._call_helper(intersection)
        self.assertIs(result, get_enum('OPPOSED'))

    def test_opposed_opp_sign_curvature_with_overlap(self):
        import bezier

        first = bezier.Curve(self.QUADRATIC1, 2)
        first._edge_index = 1
        second = bezier.Curve(self.QUADRATIC2[::-1, :], 2)
        second._edge_index = 0
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=1, index_second=0)

        with self.assertRaises(NotImplementedError):
            self._call_helper(intersection)


class Test_ignored_edge_corner(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(
            edge_tangent, corner_tangent, corner_previous_edge):
        from bezier import _surface_helpers

        return _surface_helpers.ignored_edge_corner(
            edge_tangent, corner_tangent, corner_previous_edge)

    def test_first_across(self):
        edge_tangent = np.asfortranarray([[1.0, 0.0]])
        corner_tangent = np.asfortranarray([[0.0, 1.0]])
        self.assertFalse(
            self._call_function_under_test(edge_tangent, corner_tangent, None))

    def test_outside(self):
        edge_tangent = np.asfortranarray([[-1.0, 1.0]])
        corner_tangent = np.asfortranarray([[0.5, 0.5]])
        corner_previous_edge = np.asfortranarray([
            [0.5, 2.0],
            [0.5, 0.5],
        ])
        result = self._call_function_under_test(
            edge_tangent, corner_tangent, corner_previous_edge)
        self.assertTrue(result)

    def test_straddle(self):
        edge_tangent = np.asfortranarray([[1.0, 0.0]])
        corner_tangent = np.asfortranarray([[1.0, -1.0]])
        corner_previous_edge = np.asfortranarray([
            [1.0, 1.0],
            [0.5, 0.0],
        ])
        result = self._call_function_under_test(
            edge_tangent, corner_tangent, corner_previous_edge)
        self.assertFalse(result)


class Test_ignored_double_corner(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection, tangent_s, tangent_t):
        from bezier import _surface_helpers

        return _surface_helpers.ignored_double_corner(
            intersection, tangent_s, tangent_t)

    def test_ignored(self):
        import bezier

        surface1 = bezier.Surface.from_nodes(np.asfortranarray([
            [1.0, 0.0],
            [1.5, 0.25],
            [0.5, 1.0],
        ]))
        first, _, _ = surface1.edges
        surface2 = bezier.Surface(UNIT_TRIANGLE, 1)
        _, second, _ = surface2.edges
        intersection = make_intersect(
            first, 0.0, second, 0.0,
            index_first=0, index_second=1)
        tangent_s = np.asfortranarray([[0.5, 0.25]])
        tangent_t = np.asfortranarray([[-1.0, 1.0]])

        result = self._call_function_under_test(
            intersection, tangent_s, tangent_t)
        self.assertTrue(result)

    def test_overlap_first(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        _, first, _ = surface1.edges
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [1.0, 0.0],
            [1.0, 1.0],
            [0.5, 0.25],
        ]))
        second, _, _ = surface2.edges
        intersection = make_intersect(
            first, 0.0, second, 0.0,
            index_first=1, index_second=0)
        tangent_s = np.asfortranarray([[-1.0, 1.0]])
        tangent_t = np.asfortranarray([[0.0, 1.0]])

        result = self._call_function_under_test(
            intersection, tangent_s, tangent_t)
        self.assertFalse(result)

    def test_overlap_second(self):
        import bezier

        surface1 = bezier.Surface.from_nodes(np.asfortranarray([
            [1.0, 0.0],
            [1.0, 1.0],
            [0.5, 0.25],
        ]))
        first, _, _ = surface1.edges
        surface2 = bezier.Surface(UNIT_TRIANGLE, 1)
        _, second, _ = surface2.edges
        intersection = make_intersect(
            first, 0.0, second, 0.0,
            index_first=0, index_second=1)
        tangent_s = np.asfortranarray([[0.0, 1.0]])
        tangent_t = np.asfortranarray([[-1.0, 1.0]])

        result = self._call_function_under_test(
            intersection, tangent_s, tangent_t)
        self.assertFalse(result)

    def test_segment_contained(self):
        import bezier

        surface1 = bezier.Surface.from_nodes(np.asfortranarray([
            [0.0, 0.0],
            [1.0, 0.5],
            [0.5, 1.0],
        ]))
        first, _, _ = surface1.edges
        surface2 = bezier.Surface(UNIT_TRIANGLE, 1)
        second, _, _ = surface2.edges
        intersection = make_intersect(
            first, 0.0, second, 0.0,
            index_first=0, index_second=0)
        tangent_s = np.asfortranarray([[1.0, 0.5]])
        tangent_t = np.asfortranarray([[1.0, 0.0]])

        result = self._call_function_under_test(
            intersection, tangent_s, tangent_t)
        self.assertFalse(result)


class Test_ignored_corner(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(intersection, tangent_s, tangent_t):
        from bezier import _surface_helpers

        return _surface_helpers.ignored_corner(
            intersection, tangent_s, tangent_t)

    def test_not_corner(self):
        intersection = make_intersect(None, 0.5, None, 0.5)
        result = self._call_function_under_test(intersection, None, None)
        self.assertFalse(result)

    def test_s_corner(self):
        import bezier

        surface = bezier.Surface(UNIT_TRIANGLE, degree=1, _copy=False)
        _, previous_edge, first = surface.edges
        intersection = make_intersect(first, 0.0, None, 0.5, index_first=2)

        patch = unittest.mock.patch(
            'bezier._surface_helpers.ignored_edge_corner',
            return_value=unittest.mock.sentinel.edge_result)
        with patch as mocked:
            result = self._call_function_under_test(
                intersection, unittest.mock.sentinel.tangent_s,
                unittest.mock.sentinel.tangent_t)
        self.assertIs(result, unittest.mock.sentinel.edge_result)
        self.assertEqual(mocked.call_count, 1)
        call = mocked.mock_calls[0]
        _, positional, keyword = call
        self.assertEqual(keyword, {})
        self.assertEqual(len(positional), 3)
        self.assertIs(positional[0], unittest.mock.sentinel.tangent_t)
        self.assertIs(positional[1], unittest.mock.sentinel.tangent_s)
        self.assertEqual(positional[2], previous_edge.nodes)

    def test_t_corner(self):
        import bezier

        surface = bezier.Surface(UNIT_TRIANGLE, degree=1, _copy=False)
        previous_edge, second, _ = surface.edges
        intersection = make_intersect(None, 0.5, second, 0.0, index_second=1)

        patch = unittest.mock.patch(
            'bezier._surface_helpers.ignored_edge_corner',
            return_value=unittest.mock.sentinel.edge_result)
        with patch as mocked:
            result = self._call_function_under_test(
                intersection, unittest.mock.sentinel.tangent_s,
                unittest.mock.sentinel.tangent_t)

        self.assertIs(result, unittest.mock.sentinel.edge_result)
        self.assertEqual(mocked.call_count, 1)
        call = mocked.mock_calls[0]
        _, positional, keyword = call
        self.assertEqual(keyword, {})
        self.assertEqual(len(positional), 3)
        self.assertIs(positional[0], unittest.mock.sentinel.tangent_s)
        self.assertIs(positional[1], unittest.mock.sentinel.tangent_t)
        self.assertEqual(positional[2], previous_edge.nodes)

    def test_double_corner(self):
        intersection = make_intersect(None, 0.0, None, 0.0)

        patch = unittest.mock.patch(
            'bezier._surface_helpers.ignored_double_corner',
            return_value=unittest.mock.sentinel.double_result)
        with patch as mocked:
            result = self._call_function_under_test(
                intersection, unittest.mock.sentinel.tangent_s,
                unittest.mock.sentinel.tangent_t)
            self.assertIs(result, unittest.mock.sentinel.double_result)

            mocked.assert_called_once_with(
                intersection, unittest.mock.sentinel.tangent_s,
                unittest.mock.sentinel.tangent_t)


class Test_handle_corners(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection):
        from bezier import _surface_helpers

        return _surface_helpers.handle_corners(intersection)

    def test_neither(self):
        first = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        second = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        intersection = make_intersect(
            first, 0.5, second, 0.5,
            index_first=first._edge_index,
            index_second=second._edge_index,
        )

        self.assertFalse(self._call_function_under_test(intersection))
        self.assertEqual(intersection.s, 0.5)
        self.assertIs(intersection.first, first)
        self.assertEqual(intersection.t, 0.5)
        self.assertIs(intersection.second, second)

    def test_s(self):
        third = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        first = unittest.mock.Mock(
            _edge_index=2, _next_edge=third,
            spec=['_edge_index', '_next_edge'],
        )
        second = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        intersection = make_intersect(
            first, 1.0, second, 0.25,
            index_first=first._edge_index,
            index_second=second._edge_index,
        )

        self.assertTrue(self._call_function_under_test(intersection))
        self.assertEqual(intersection.s, 0.0)
        self.assertIs(intersection.first, third)
        self.assertEqual(intersection.t, 0.25)
        self.assertIs(intersection.second, second)

    def test_t(self):
        first = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        third = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        second = unittest.mock.Mock(
            _edge_index=0, _next_edge=third,
            spec=['_edge_index', '_next_edge'],
        )
        intersection = make_intersect(
            first, 0.75, second, 1.0,
            index_first=first._edge_index,
            index_second=second._edge_index,
        )

        self.assertTrue(self._call_function_under_test(intersection))
        self.assertEqual(intersection.s, 0.75)
        self.assertIs(intersection.first, first)
        self.assertEqual(intersection.t, 0.0)
        self.assertIs(intersection.second, third)


class Test_same_intersection(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection1, intersection2, **kwargs):
        from bezier import _surface_helpers

        return _surface_helpers.same_intersection(
            intersection1, intersection2, **kwargs)

    @staticmethod
    def _make_one(index1, s, index2, t):
        first = unittest.mock.Mock(_edge_index=index1, spec=['_edge_index'])
        second = unittest.mock.Mock(_edge_index=index2, spec=['_edge_index'])
        return make_intersect(
            first, s, second, t, index_first=index1, index_second=index2)

    def test_same(self):
        intersection = self._make_one(10, 0.5, 99, 0.75)
        result = self._call_function_under_test(intersection, intersection)
        self.assertTrue(result)

    def test_almost_same(self):
        intersection1 = self._make_one(10, 0.5, 99, 0.75)
        intersection2 = self._make_one(10, 0.5, 99, 0.875)
        result = self._call_function_under_test(intersection1, intersection2)
        self.assertFalse(result)
        result = self._call_function_under_test(
            intersection1, intersection2, wiggle=0.5)
        self.assertTrue(result)

    def test_different_edge(self):
        intersection1 = self._make_one(10, 0.5, 99, 0.5)
        intersection2 = self._make_one(10, 0.5, 98, 0.5)
        intersection3 = self._make_one(11, 0.5, 99, 0.5)
        self.assertFalse(
            self._call_function_under_test(intersection1, intersection2))
        self.assertFalse(
            self._call_function_under_test(intersection1, intersection3))

    def test_different_param(self):
        intersection1 = self._make_one(1, 0.5, 9, 0.5)
        intersection2 = self._make_one(1, 0.75, 9, 0.5)
        intersection3 = self._make_one(1, 0.5, 9, 0.75)
        self.assertFalse(
            self._call_function_under_test(intersection1, intersection2))
        self.assertFalse(
            self._call_function_under_test(intersection1, intersection3))


class Test_verify_duplicates(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(duplicates, uniques):
        from bezier import _surface_helpers

        return _surface_helpers.verify_duplicates(duplicates, uniques)

    @staticmethod
    def _make_one(index1, s, index2, t):
        first = unittest.mock.Mock(_edge_index=index1, spec=['_edge_index'])
        second = unittest.mock.Mock(_edge_index=index2, spec=['_edge_index'])
        return make_intersect(
            first, s, second, t, index_first=index1, index_second=index2)

    def test_empty(self):
        self.assertIsNone(self._call_function_under_test([], []))

    def test_success(self):
        uniq = self._make_one(1, 0.0, 2, 0.25)
        self.assertIsNone(
            self._call_function_under_test([uniq], [uniq]))

    def test_success_triple(self):
        uniq = self._make_one(1, 0.0, 2, 0.0)
        self.assertIsNone(
            self._call_function_under_test([uniq, uniq, uniq], [uniq]))

    def test_failed_uniqueness(self):
        uniq = self._make_one(1, 0.375, 2, 0.75)
        with self.assertRaises(ValueError):
            self._call_function_under_test([], [uniq, uniq])

    def test_bad_duplicate(self):
        dupe = self._make_one(1, 0.75, 2, 0.25)
        uniq = self._make_one(1, 0.25, 2, 0.75)
        with self.assertRaises(ValueError):
            self._call_function_under_test([dupe], [uniq])

    def test_bad_single_corner(self):
        uniq = self._make_one(1, 0.125, 2, 0.125)
        with self.assertRaises(ValueError):
            self._call_function_under_test([uniq], [uniq])

    def test_bad_double_corner(self):
        uniq = self._make_one(1, 0.0, 2, 1.0)
        with self.assertRaises(ValueError):
            self._call_function_under_test([uniq, uniq, uniq], [uniq])

    def test_bad_count(self):
        uniq = self._make_one(1, 0.375, 2, 0.75)
        with self.assertRaises(ValueError):
            self._call_function_under_test([uniq, uniq], [uniq])


class Test_to_front(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection, intersections, unused):
        from bezier import _surface_helpers

        return _surface_helpers.to_front(
            intersection, intersections, unused)

    def test_no_change(self):
        intersection = make_intersect(None, 0.5, None, 0.5)
        result = self._call_function_under_test(intersection, [], [])
        self.assertIs(result, intersection)

    def test_remove_from_unused(self):
        intersection = make_intersect(None, 0.5, None, 0.5)
        unused = [intersection]
        result = self._call_function_under_test(intersection, [], unused)
        self.assertIs(result, intersection)
        self.assertEqual(unused, [])

    def test_move_s(self):
        from bezier import _intersection_helpers

        third = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        first = unittest.mock.Mock(
            _edge_index=2, _next_edge=third,
            spec=['_edge_index', '_next_edge'],
        )
        second = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        intersection = make_intersect(
            first, 1.0, second, 0.5,
            index_first=first._edge_index,
            index_second=second._edge_index,
            interior_curve=unittest.mock.sentinel.interior_curve,
        )

        result = self._call_function_under_test(intersection, [], [])
        self.assertIsNot(result, intersection)
        self.assertIsInstance(result, _intersection_helpers.Intersection)
        self.assertIs(result.first, third)
        self.assertEqual(result.s, 0.0)
        self.assertIs(result.second, second)
        self.assertEqual(result.t, 0.5)
        self.assertIs(
            result.interior_curve, unittest.mock.sentinel.interior_curve)

    def test_move_s_to_existing(self):
        third = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        first = unittest.mock.Mock(
            _edge_index=1, _next_edge=third,
            spec=['_edge_index', '_next_edge'],
        )
        second = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        intersection = make_intersect(
            first, 1.0, second, 0.5,
            index_first=first._edge_index,
            index_second=second._edge_index,
        )

        existing_int = make_intersect(
            third, 0.0, second, 0.5,
            index_first=third._edge_index,
            index_second=second._edge_index,
        )
        result = self._call_function_under_test(
            intersection, [existing_int], [])
        self.assertIs(result, existing_int)

    def test_move_t(self):
        from bezier import _intersection_helpers

        first = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        third = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        second = unittest.mock.Mock(
            _edge_index=1, _next_edge=third,
            spec=['_edge_index', '_next_edge'],
        )
        intersection = make_intersect(
            first, 0.5, second, 1.0,
            interior_curve=unittest.mock.sentinel.interior_curve,
            index_first=first._edge_index,
            index_second=second._edge_index,
        )

        result = self._call_function_under_test(intersection, [], [])
        self.assertIsNot(result, intersection)
        self.assertIsInstance(result, _intersection_helpers.Intersection)
        self.assertIs(result.first, first)
        self.assertEqual(result.s, 0.5)
        self.assertIs(result.second, third)
        self.assertEqual(result.t, 0.0)
        self.assertIs(
            result.interior_curve, unittest.mock.sentinel.interior_curve)

    def test_move_t_to_existing(self):
        first = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        third = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        second = unittest.mock.Mock(
            _edge_index=0, _next_edge=third,
            spec=['_edge_index', '_next_edge'],
        )
        intersection = make_intersect(
            first, 0.5, second, 1.0,
            index_first=first._edge_index,
            index_second=second._edge_index,
        )

        existing_int = make_intersect(
            first, 0.5, third, 0.0,
            index_first=first._edge_index,
            index_second=third._edge_index,
        )
        result = self._call_function_under_test(
            intersection, [existing_int], [])
        self.assertIs(result, existing_int)


class Test_get_next_first(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection, intersections):
        from bezier import _surface_helpers

        return _surface_helpers.get_next_first(intersection, intersections)

    def test_move_to_corner(self):
        from bezier import _intersection_helpers

        first = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        intersection = make_intersect(
            first, 0.25, None, None, index_first=first._edge_index)
        result = self._call_function_under_test(intersection, [])
        self.assertIsInstance(result, _intersection_helpers.Intersection)
        self.assertIs(result.first, first)
        self.assertEqual(result.s, 1.0)
        self.assertIsNone(result.second)
        self.assertIsNone(result.t)
        self.assertIs(result.interior_curve, get_enum('FIRST'))

    def test_move_to_existing(self):
        first = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        not_first = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        intersection = make_intersect(
            first, 0.25, None, None, index_first=first._edge_index)
        intersections = [
            # An "unacceptable" intersection with ``other_int.first is first``
            # and ``other_s > s``.
            make_intersect(
                first, 0.375, None, None,
                interior_curve=get_enum('OPPOSED'),
                index_first=first._edge_index,
            ),
            # An "acceptable" intersection that will be overtaken by the
            # next since 0.25 < 0.5 < 0.875.
            make_intersect(
                first, 0.875, None, None,
                interior_curve=get_enum('SECOND'),
                index_first=first._edge_index,
            ),
            make_intersect(
                first, 0.5, None, None,
                interior_curve=get_enum('FIRST'),
                index_first=first._edge_index,
            ),
            # On a different curve.
            make_intersect(
                not_first, None, None, None,
                index_first=not_first._edge_index,
            ),
            # Same curve, but before.
            make_intersect(
                first, 0.125, None, None,
                interior_curve=get_enum('FIRST'),
                index_first=first._edge_index,
            ),
            # Past the already accepted intersection.
            make_intersect(
                first, 0.625, None, None,
                interior_curve=get_enum('FIRST'),
                index_first=first._edge_index,
            ),
        ]
        result = self._call_function_under_test(intersection, intersections)
        self.assertIs(result, intersections[2])

    def test_move_to_intersected_corner(self):
        first = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        intersection = make_intersect(
            first, 0.625, None, None, index_first=first._edge_index)
        intersections = [
            # An "unacceptable" intersection that is still OK since a corner.
            make_intersect(
                first, 1.0, None, None,
                interior_curve=get_enum('TANGENT_FIRST'),
                index_first=first._edge_index,
            ),
        ]
        result = self._call_function_under_test(intersection, intersections)
        self.assertIs(result, intersections[0])


class Test_get_next_second(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection, intersections):
        from bezier import _surface_helpers

        return _surface_helpers.get_next_second(intersection, intersections)

    def test_move_to_corner(self):
        from bezier import _intersection_helpers

        second = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        intersection = make_intersect(
            None, None, second, 0.625, index_second=second._edge_index)
        result = self._call_function_under_test(intersection, [])
        self.assertIsInstance(result, _intersection_helpers.Intersection)
        self.assertIsNone(result.first)
        self.assertIsNone(result.s)
        self.assertIs(result.second, second)
        self.assertEqual(result.t, 1.0)
        self.assertIs(result.interior_curve, get_enum('SECOND'))

    def test_move_to_existing(self):
        second = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        not_second = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        intersection = make_intersect(
            None, None, second, 0.125, index_second=second._edge_index)
        intersections = [
            # An "unacceptable" intersection with
            # ``other_int.second is second`` and ``other_t > t``.
            make_intersect(
                None, None, second, 0.5,
                interior_curve=get_enum('TANGENT_SECOND'),
                index_second=second._edge_index,
            ),
            # An "acceptable" intersection that will be overtaken by the
            # next since 0.125 < 0.625 < 0.75.
            make_intersect(
                None, None, second, 0.75,
                interior_curve=get_enum('FIRST'),
                index_second=second._edge_index,
            ),
            make_intersect(
                None, None, second, 0.625,
                interior_curve=get_enum('SECOND'),
                index_second=second._edge_index,
            ),
            # On a different curve.
            make_intersect(
                None, None, not_second, None,
                index_second=not_second._edge_index,
            ),
            # Same curve, but before.
            make_intersect(
                None, None, second, 0.0625,
                interior_curve=get_enum('FIRST'),
                index_second=second._edge_index,
            ),
            # Past the already accepted intersection.
            make_intersect(
                None, None, second, 0.6875,
                interior_curve=get_enum('SECOND'),
                index_second=second._edge_index,
            ),
        ]
        result = self._call_function_under_test(intersection, intersections)
        self.assertIs(result, intersections[2])

    def test_move_to_intersected_corner(self):
        second = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        intersection = make_intersect(
            None, None, second, 0.5,
            index_second=second._edge_index)
        intersections = [
            # An "unacceptable" intersection that is still OK since a corner.
            make_intersect(
                None, None, second, 1.0,
                interior_curve=get_enum('TANGENT_FIRST'),
                index_second=second._edge_index,
            ),
        ]
        result = self._call_function_under_test(intersection, intersections)
        self.assertIs(result, intersections[0])


class Test_get_next(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersection, intersections, unused):
        from bezier import _surface_helpers

        return _surface_helpers.get_next(
            intersection, intersections, unused)

    def test_remove_from_unused(self):
        # Also tests branch through "first".
        unused = [unittest.mock.sentinel.result]
        intersection = make_intersect(
            None, None, None, None, interior_curve=get_enum('FIRST'))

        patch = unittest.mock.patch(
            'bezier._surface_helpers.get_next_first',
            return_value=unittest.mock.sentinel.result)
        with patch as mocked:
            result = self._call_function_under_test(
                intersection, unittest.mock.sentinel.intersections, unused)
            self.assertIs(result, unittest.mock.sentinel.result)
            self.assertEqual(unused, [])

            mocked.assert_called_once_with(
                intersection, unittest.mock.sentinel.intersections)

    def test_second(self):
        intersection = make_intersect(
            None, None, None, None, interior_curve=get_enum('SECOND'))

        patch = unittest.mock.patch(
            'bezier._surface_helpers.get_next_second',
            return_value=unittest.mock.sentinel.result)
        with patch as mocked:
            result = self._call_function_under_test(
                intersection, unittest.mock.sentinel.intersections, [])
            self.assertIs(result, unittest.mock.sentinel.result)

            mocked.assert_called_once_with(
                intersection, unittest.mock.sentinel.intersections)

    def test_invalid_classification(self):
        intersection = make_intersect(
            None, None, None, None, interior_curve=get_enum('OPPOSED'))
        with self.assertRaises(ValueError):
            self._call_function_under_test(intersection, [], [])


class Test_ends_to_curve(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(start_node, end_node):
        from bezier import _surface_helpers

        return _surface_helpers.ends_to_curve(start_node, end_node)

    def test_bad_classification(self):
        start_node = make_intersect(None, 0.5, None, 0.5)
        end_node = make_intersect(None, 0.75, None, 0.75)
        with self.assertRaises(ValueError):
            self._call_function_under_test(start_node, end_node)

    def _on_different_curves(self, interior_curve):
        first1 = unittest.mock.Mock(_edge_index=0, spec=['_edge_index'])
        second1 = unittest.mock.Mock(_edge_index=2, spec=['_edge_index'])
        start_node = make_intersect(
            first1, 0.5, second1, 0.5,
            interior_curve=interior_curve,
            index_first=0, index_second=2)
        first2 = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        second2 = unittest.mock.Mock(_edge_index=1, spec=['_edge_index'])
        end_node = make_intersect(
            first2, 0.5, second2, 0.5,
            index_first=1, index_second=1)
        with self.assertRaises(ValueError):
            self._call_function_under_test(start_node, end_node)

    def test_first_on_different_curves(self):
        self._on_different_curves(get_enum('FIRST'))

    def test_second_on_different_curves(self):
        self._on_different_curves(get_enum('SECOND'))

    def test_first(self):
        import bezier

        first = bezier.Curve.from_nodes(np.asfortranarray([
            [0.0, 1.0],
            [1.0, 3.0],
        ]))
        first._edge_index = 0
        start_node = make_intersect(
            first, 0.5, None, None,
            interior_curve=get_enum('FIRST'),
            index_first=first._edge_index)
        end_node = make_intersect(
            first, 0.75, None, None,
            index_first=first._edge_index)

        result = self._call_function_under_test(start_node, end_node)
        self.assertIsInstance(result, bezier.Curve)
        expected = np.asfortranarray([
            [0.5, 2.0],
            [0.75, 2.5],
        ])
        self.assertEqual(result._nodes, expected)
        self.assertEqual(result.start, 0.5)
        self.assertEqual(result.end, 0.75)
        self.assertIs(result.root, first)

    def test_second(self):
        import bezier

        nodes = np.asfortranarray([
            [4.0, -1.0],
            [2.0, 1.0],
        ])
        second = bezier.Curve(nodes, 1)
        second._edge_index = 2
        start_node = make_intersect(
            None, None, second, 0.125,
            interior_curve=get_enum('SECOND'),
            index_second=second._edge_index)
        end_node = make_intersect(
            None, None, second, 0.25,
            index_second=second._edge_index)

        result = self._call_function_under_test(start_node, end_node)
        self.assertIsInstance(result, bezier.Curve)
        expected = np.asfortranarray([
            [3.75, -0.75],
            [3.5, -0.5],
        ])
        self.assertEqual(result._nodes, expected)
        self.assertEqual(result.start, 0.125)
        self.assertEqual(result.end, 0.25)
        self.assertIs(result.root, second)


class Test_to_curved_polygon(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(surface):
        from bezier import _surface_helpers

        return _surface_helpers.to_curved_polygon(surface)

    def test_it(self):
        import bezier

        surface = bezier.Surface(UNIT_TRIANGLE, 1)
        result = self._call_function_under_test(surface)
        self.assertIsInstance(result, bezier.CurvedPolygon)
        self.assertEqual(result._num_sides, 3)
        expected = np.asfortranarray(UNIT_TRIANGLE[(0, 1), :])
        self.assertEqual(result._edges[0].nodes, expected)
        expected = np.asfortranarray(UNIT_TRIANGLE[(1, 2), :])
        self.assertEqual(result._edges[1].nodes, expected)
        expected = np.asfortranarray(UNIT_TRIANGLE[(2, 0), :])
        self.assertEqual(result._edges[2].nodes, expected)


class Test_no_intersections(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(surface1, surface2):
        from bezier import _surface_helpers

        return _surface_helpers.no_intersections(surface1, surface2)

    def test_disjoint(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        surface2 = bezier.Surface(
            UNIT_TRIANGLE + np.asfortranarray([[5.0, 0.0]]), 1)
        result = self._call_function_under_test(surface1, surface2)
        self.assertEqual(result, [])

    def test_first_contained(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        surface2 = bezier.Surface(
            4.0 * UNIT_TRIANGLE - np.asfortranarray([[1.0, 1.0]]), 1)

        patch = unittest.mock.patch(
            'bezier._surface_helpers.to_curved_polygon',
            return_value=unittest.mock.sentinel.curved)
        with patch as mocked:
            result = self._call_function_under_test(surface1, surface2)
            self.assertEqual(result, [unittest.mock.sentinel.curved])

            mocked.assert_called_once_with(surface1)

    def test_second_contained(self):
        import bezier

        surface1 = bezier.Surface(
            4.0 * UNIT_TRIANGLE - np.asfortranarray([[1.0, 1.0]]), 1)
        surface2 = bezier.Surface(UNIT_TRIANGLE, 1)

        patch = unittest.mock.patch(
            'bezier._surface_helpers.to_curved_polygon',
            return_value=unittest.mock.sentinel.curved)
        with patch as mocked:
            result = self._call_function_under_test(surface1, surface2)
            self.assertEqual(result, [unittest.mock.sentinel.curved])

            mocked.assert_called_once_with(surface2)


class Test_tangent_only_intersections(unittest.TestCase):

    @staticmethod
    def _call_function_under_test(intersections, surface1, surface2):
        from bezier import _surface_helpers

        return _surface_helpers.tangent_only_intersections(
            intersections, surface1, surface2)

    def test_too_few_types(self):
        with self.assertRaises(ValueError):
            self._call_function_under_test([], None, None)

    def test_too_many_types(self):
        int1 = unittest.mock.Mock(interior_curve=get_enum('FIRST'))
        int2 = unittest.mock.Mock(interior_curve=get_enum('SECOND'))
        with self.assertRaises(ValueError):
            self._call_function_under_test([int1, int2], None, None)

    def test_bad_types(self):
        intersection = unittest.mock.Mock(interior_curve=get_enum('FIRST'))
        with self.assertRaises(ValueError):
            self._call_function_under_test([intersection], None, None)

    def test_ignored_types(self):
        intersection = unittest.mock.Mock(interior_curve=get_enum('OPPOSED'))
        result = self._call_function_under_test([intersection], None, None)
        self.assertEqual(result, [])

        intersection = unittest.mock.Mock(
            interior_curve=get_enum('IGNORED_CORNER'))
        result = self._call_function_under_test([intersection], None, None)
        self.assertEqual(result, [])

    def test_first(self):
        intersection = unittest.mock.Mock(
            interior_curve=get_enum('TANGENT_FIRST'))

        patch = unittest.mock.patch(
            'bezier._surface_helpers.to_curved_polygon',
            return_value=unittest.mock.sentinel.curved)
        with patch as mocked:
            result = self._call_function_under_test(
                [intersection], unittest.mock.sentinel.surface1, None)
            self.assertEqual(result, [unittest.mock.sentinel.curved])

            mocked.assert_called_once_with(unittest.mock.sentinel.surface1)

    def test_second(self):
        intersection = unittest.mock.Mock(
            interior_curve=get_enum('TANGENT_SECOND'))

        patch = unittest.mock.patch(
            'bezier._surface_helpers.to_curved_polygon',
            return_value=unittest.mock.sentinel.curved)
        with patch as mocked:
            result = self._call_function_under_test(
                [intersection], None, unittest.mock.sentinel.surface2)
            self.assertEqual(result, [unittest.mock.sentinel.curved])

            mocked.assert_called_once_with(unittest.mock.sentinel.surface2)


class Test_basic_interior_combine(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(intersections, **kwargs):
        from bezier import _surface_helpers

        return _surface_helpers.basic_interior_combine(
            intersections, **kwargs)

    def test_it(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        edges1 = surface1.edges
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [0.5, 0.25],
            [1.0, 0.25],
            [0.75, 1.0],
        ]))
        edges2 = surface2.edges

        intersection1 = make_intersect(
            edges1[1], 0.25, edges2[0], 0.4375,
            interior_curve=get_enum('FIRST'),
            index_first=1, index_second=0,
        )
        intersection2 = make_intersect(
            edges1[1], 0.5, edges2[2], 0.75,
            interior_curve=get_enum('SECOND'),
            index_first=1, index_second=2,
        )

        result = self._call_function_under_test(
            [intersection1, intersection2])
        self.assertEqual(len(result), 1)
        curved_polygon = result[0]
        self.assertIsInstance(curved_polygon, bezier.CurvedPolygon)
        self.assertEqual(curved_polygon.num_sides, 3)
        edge1, edge2, edge3 = curved_polygon._edges

        # First edge.
        self.assertEqual(edge1.start, 0.75)
        self.assertEqual(edge1.end, 1.0)
        expected = np.asfortranarray([
            [0.5625, 0.4375],
            [0.5, 0.25],
        ])
        self.assertEqual(edge1.nodes, expected)
        # Second edge.
        self.assertEqual(edge2.start, 0.0)
        self.assertEqual(edge2.end, 0.4375)
        expected = np.asfortranarray([
            [0.5, 0.25],
            [0.71875, 0.25],
        ])
        self.assertEqual(edge2.nodes, expected)
        # Third edge.
        self.assertEqual(edge3.start, 0.25)
        self.assertEqual(edge3.end, 0.5)
        expected = np.asfortranarray([
            [0.75, 0.25],
            [0.5, 0.5],
        ])
        self.assertEqual(edge3.nodes, expected)

    def test_corner_node_next(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        edges1 = surface1._get_edges()
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [0.0, 0.125],
            [0.875, 0.0],
            [0.25, 0.75],
        ]))
        edges2 = surface2._get_edges()

        intersections = [
            make_intersect(
                edges1[0], 0.875, edges2[1], 0.0,
                interior_curve=get_enum('SECOND'),
                index_first=0, index_second=1,
            ),
            make_intersect(
                edges1[1], 0.75, edges2[2], 0.0,
                interior_curve=get_enum('SECOND'),
                index_first=1, index_second=2,
            ),
            make_intersect(
                edges1[2], 0.875, edges2[0], 0.0,
                interior_curve=get_enum('SECOND'),
                index_first=2, index_second=0,
            ),
        ]
        result = self._call_function_under_test(intersections)

        self.assertEqual(len(result), 1)
        curved_polygon = result[0]
        self.assertIsInstance(curved_polygon, bezier.CurvedPolygon)
        self.assertEqual(curved_polygon.num_sides, 3)

        self.assertEqual(curved_polygon._edges[0].nodes, np.asfortranarray([
            [0.0, 0.125],
            [0.875, 0.0],
        ]))
        self.assertEqual(curved_polygon._edges[1].nodes, np.asfortranarray([
            [0.875, 0.0],
            [0.25, 0.75],
        ]))
        self.assertEqual(curved_polygon._edges[2].nodes, np.asfortranarray([
            [0.25, 0.75],
            [0.0, 0.125],
        ]))

    def _too_many_edges_helper(self, to_front, get_next, **kwargs):
        start = make_intersect(
            None, 0.0, None, 0.0, interior_curve=get_enum('SECOND'))
        with self.assertRaises(RuntimeError):
            self._call_function_under_test([start], **kwargs)

        max_edges = kwargs.pop('max_edges', 10)
        self.assertEqual(kwargs, {})

        self.assertEqual(to_front.call_count, max_edges)
        self.assertEqual(get_next.call_count, max_edges + 1)

    @unittest.mock.patch(
        'bezier._surface_helpers.get_next',
        return_value=unittest.mock.sentinel.next_)
    @unittest.mock.patch(
        'bezier._surface_helpers.to_front',
        return_value=unittest.mock.sentinel.front)
    def test_too_many_edges(self, to_front, get_next):
        self._too_many_edges_helper(to_front, get_next)

    @unittest.mock.patch(
        'bezier._surface_helpers.get_next',
        return_value=unittest.mock.sentinel.next_)
    @unittest.mock.patch(
        'bezier._surface_helpers.to_front',
        return_value=unittest.mock.sentinel.front)
    def test_too_many_edges_explicit_max(self, to_front, get_next):
        self._too_many_edges_helper(to_front, get_next, max_edges=3)


class Test_combine_intersections(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(intersections, surface1, surface2):
        from bezier import _surface_helpers

        return _surface_helpers.combine_intersections(
            intersections, surface1, surface2)

    def test_empty(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [-1.0, 0.0],
            [-1.0, 1.0],
            [-2.0, 1.0],
        ]))
        result = self._call_function_under_test([], surface1, surface2)
        self.assertEqual(result, [])

    def test_basic(self):
        import bezier

        surface1 = bezier.Surface(UNIT_TRIANGLE, 1)
        edges1 = surface1._get_edges()
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [0.75, -0.25],
            [0.75, 0.75],
            [-0.25, 0.75],
        ]))
        edges2 = surface2._get_edges()
        intersections = [
            make_intersect(
                edges1[0], 0.75, edges2[0], 0.25,
                interior_curve=get_enum('SECOND'),
                index_first=0, index_second=0,
            ),
            make_intersect(
                edges1[0], 0.5, edges2[2], 0.75,
                interior_curve=get_enum('FIRST'),
                index_first=0, index_second=2,
            ),
            make_intersect(
                edges1[1], 0.25, edges2[0], 0.5,
                interior_curve=get_enum('FIRST'),
                index_first=1, index_second=0,
            ),
            make_intersect(
                edges1[1], 0.75, edges2[1], 0.5,
                interior_curve=get_enum('SECOND'),
                index_first=1, index_second=1,
            ),
            make_intersect(
                edges1[2], 0.25, edges2[1], 0.75,
                interior_curve=get_enum('FIRST'),
                index_first=2, index_second=1,
            ),
            make_intersect(
                edges1[2], 0.5, edges2[2], 0.25,
                interior_curve=get_enum('SECOND'),
                index_first=2, index_second=2,
            ),
        ]
        result = self._call_function_under_test(
            intersections, surface1, surface2)

        self.assertEqual(len(result), 1)
        curved_polygon = result[0]
        self.assertIsInstance(curved_polygon, bezier.CurvedPolygon)
        self.assertEqual(curved_polygon.num_sides, 6)

        edge_choices = surface1._get_edges() + surface2._get_edges()
        start_vals = [0.25, 0.5, 0.25, 0.25, 0.5, 0.25]
        end_vals = [0.75, 0.75, 0.5, 0.75, 0.75, 0.5]
        edge_inds = [5, 0, 3, 1, 4, 2]
        for index in range(6):
            edge = curved_polygon._edges[index]
            self.assertEqual(edge.start, start_vals[index])
            self.assertEqual(edge.end, end_vals[index])
            self.assertIs(edge.root, edge_choices[edge_inds[index]])

    def test_tangent(self):
        import bezier

        surface1 = bezier.Surface.from_nodes(np.asfortranarray([
            [0.0, 0.0],
            [0.5, -0.5],
            [1.0, 0.0],
            [0.25, 0.5],
            [0.75, 0.5],
            [0.5, 1.0],
        ]))
        edges = surface1.edges
        first, _, _ = edges
        surface2 = bezier.Surface.from_nodes(np.asfortranarray([
            [-1.0, -0.25],
            [2.0, -0.25],
            [0.5, 1.5],
        ]))
        second, _, _ = surface2.edges

        intersection = make_intersect(
            first, 0.5, second, 0.5, interior_curve=get_enum('TANGENT_FIRST'))
        result = self._call_function_under_test(
            [intersection], surface1, surface2)
        self.assertEqual(len(result), 1)
        curved_polygon = result[0]
        self.assertIsInstance(curved_polygon, bezier.CurvedPolygon)
        self.assertEqual(curved_polygon.num_sides, 3)

        for index in range(3):
            self.assertEqual(
                curved_polygon._edges[index].nodes,
                edges[index].nodes)


class Test__evaluate_barycentric(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, lambda1, lambda2, lambda3):
        from bezier import _surface_helpers

        return _surface_helpers._evaluate_barycentric(
            nodes, degree, lambda1, lambda2, lambda3)

    def test_linear(self):
        lambda_vals = (0.25, 0.5, 0.25)
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [1.0, 0.5],
            [0.0, 1.25],
        ])

        expected = np.asfortranarray([[0.5, 0.5625]])
        result = self._call_function_under_test(nodes, 1, *lambda_vals)
        self.assertEqual(result, expected)

    def test_quadratic(self):
        lambda_vals = (0.0, 0.25, 0.75)
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [0.5, 0.0],
            [1.0, 0.5],
            [0.5, 1.25],
            [0.0, 1.25],
            [0.0, 0.5],
        ])

        expected = np.asfortranarray([[0.0625, 0.78125]])
        result = self._call_function_under_test(nodes, 2, *lambda_vals)
        self.assertEqual(result, expected)

    def test_quadratic_dimension3(self):
        lambda_vals = (0.125, 0.375, 0.5)
        nodes = np.asfortranarray([
            [0.0, 0.0, 1.0],
            [0.5, 0.0, 0.25],
            [1.0, 0.5, 0.0],
            [0.5, 1.25, 1.25],
            [0.0, 1.25, 0.5],
            [0.0, 0.5, -1.0],
        ])

        expected = np.asfortranarray([[0.25, 0.8203125, 0.1328125]])
        result = self._call_function_under_test(nodes, 2, *lambda_vals)
        self.assertEqual(result, expected)

    def test_cubic(self):
        lambda_vals = (0.125, 0.5, 0.375)
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [0.25, 0.0],
            [0.75, 0.25],
            [1.0, 0.0],
            [0.0, 0.25],
            [0.375, 0.25],
            [0.5, 0.25],
            [0.0, 0.5],
            [0.25, 0.75],
            [0.0, 1.0],
        ])

        expected = np.asfortranarray([[0.447265625, 0.37060546875]])
        result = self._call_function_under_test(nodes, 3, *lambda_vals)
        self.assertEqual(result, expected)

    def test_quartic(self):
        import math

        # Use a fixed seed so the test is deterministic and round
        # the nodes to 8 bits of precision to avoid round-off.
        nodes = utils.get_random_nodes(
            shape=(15, 2), seed=11112222, num_bits=8)

        lambda_vals = (0.125, 0.375, 0.5)
        index = 0
        expected = np.asfortranarray([[0.0, 0.0]])
        for k in range(4 + 1):
            for j in range(4 + 1 - k):
                i = 4 - j - k
                denom = (math.factorial(i) * math.factorial(j) *
                         math.factorial(k))
                coeff = 24 / denom
                expected += (
                    coeff * lambda_vals[0]**i * lambda_vals[1]**j *
                    lambda_vals[2]**k * nodes[[index], :])
                index += 1

        result = self._call_function_under_test(nodes, 4, *lambda_vals)
        self.assertEqual(result, expected)


@utils.needs_surface_speedup
class Test_speedup_evaluate_barycentric(Test__evaluate_barycentric):

    @staticmethod
    def _call_function_under_test(nodes, degree, lambda1, lambda2, lambda3):
        from bezier import _surface_speedup

        return _surface_speedup.evaluate_barycentric(
            nodes, degree, lambda1, lambda2, lambda3)


class Test__evaluate_barycentric_multi(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, param_vals, dimension):
        from bezier import _surface_helpers

        return _surface_helpers._evaluate_barycentric_multi(
            nodes, degree, param_vals, dimension)

    def test_basic(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [2.0, 1.0],
            [-3.0, 2.0],
        ])
        expected = np.asfortranarray([
            [0.0, 0.0],
            [2.0, 1.0],
            [-0.5, 1.5],
        ])

        param_vals = np.asfortranarray([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.5, 0.5],
        ])
        result = self._call_function_under_test(nodes, 1, param_vals, 2)
        self.assertEqual(result, expected)

    def test_outside_domain(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [3.0, -1.0],
            [1.0, 0.0],
        ])
        expected = np.asfortranarray([
            [1.0, -0.25],
            [0.0, 1.0],
            [2.375, -0.75],
        ])

        param_vals = np.asfortranarray([
            [0.25, 0.25, 0.25],
            [-1.0, -1.0, 3.0],
            [0.125, 0.75, 0.125],
        ])
        result = self._call_function_under_test(nodes, 1, param_vals, 2)
        self.assertEqual(result, expected)


@utils.needs_surface_speedup
class Test_speedup_evaluate_barycentric_multi(
        Test__evaluate_barycentric_multi):

    @staticmethod
    def _call_function_under_test(nodes, degree, param_vals, dimension):
        from bezier import _surface_speedup

        return _surface_speedup.evaluate_barycentric_multi(
            nodes, degree, param_vals, dimension)


class Test__evaluate_cartesian_multi(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree, param_vals, dimension):
        from bezier import _surface_helpers

        return _surface_helpers._evaluate_cartesian_multi(
            nodes, degree, param_vals, dimension)

    def test_basic(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [1.0, 0.75],
            [2.0, 1.0],
            [-1.5, 1.0],
            [-0.5, 1.5],
            [-3.0, 2.0],
        ])
        expected = np.asfortranarray([
            [-1.75, 1.75],
            [0.0, 0.0],
            [0.25, 1.0625],
            [-0.625, 1.046875],
        ])

        param_vals = np.asfortranarray([
            [0.25, 0.75],
            [0.0, 0.0],
            [0.5, 0.25],
            [0.25, 0.375],
        ])
        result = self._call_function_under_test(nodes, 2, param_vals, 2)
        self.assertEqual(result, expected)

    def test_outside_domain(self):
        nodes = np.asfortranarray([
            [0.0, 2.0],
            [1.0, 1.0],
            [1.0, 0.0],
        ])
        expected = np.asfortranarray([
            [0.5, 1.25],
            [2.0, -3.0],
            [0.875, 1.0],
        ])

        param_vals = np.asfortranarray([
            [0.25, 0.25],
            [-1.0, 3.0],
            [0.75, 0.125],
        ])
        result = self._call_function_under_test(nodes, 1, param_vals, 2)
        self.assertEqual(result, expected)


@utils.needs_surface_speedup
class Test_speedup_evaluate_cartesian_multi(Test__evaluate_cartesian_multi):

    @staticmethod
    def _call_function_under_test(nodes, degree, param_vals, dimension):
        from bezier import _surface_speedup

        return _surface_speedup.evaluate_cartesian_multi(
            nodes, degree, param_vals, dimension)


class Test__compute_edge_nodes(utils.NumPyTestCase):

    @staticmethod
    def _call_function_under_test(nodes, degree):
        from bezier import _surface_helpers

        return _surface_helpers._compute_edge_nodes(nodes, degree)

    def _check(self, nodes, degree, expected1, expected2, expected3):
        nodes1, nodes2, nodes3 = self._call_function_under_test(nodes, degree)
        self.assertEqual(nodes1, expected1)
        self.assertEqual(nodes2, expected2)
        self.assertEqual(nodes3, expected3)

    def test_linear(self):
        nodes = np.asfortranarray([
            [1.0, 2.0],
            [4.0, 2.5],
            [0.0, 4.0],
        ])
        p100, p010, p001 = nodes

        self._check(
            nodes, 1,
            np.asfortranarray(np.vstack([p100, p010])),
            np.asfortranarray(np.vstack([p010, p001])),
            np.asfortranarray(np.vstack([p001, p100])))

    def test_quadratic(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [1.25, 0.5],
            [2.0, 1.0],
            [-1.5, 0.75],
            [0.0, 2.0],
            [-3.0, 3.0],
        ])
        p200, p110, p020, p101, p011, p002 = nodes

        self._check(
            nodes, 2,
            np.asfortranarray(np.vstack([p200, p110, p020])),
            np.asfortranarray(np.vstack([p020, p011, p002])),
            np.asfortranarray(np.vstack([p002, p101, p200])))

    def test_cubic(self):
        nodes = np.asfortranarray([
            [0.0, 0.0],
            [0.328125, 0.1484375],
            [0.65625, 0.1484375],
            [1.0, 0.0],
            [0.1484375, 0.328125],
            [0.5, 0.5],
            [1.0, 0.53125],
            [0.1484375, 0.65625],
            [0.53125, 1.0],
            [0.0, 1.0],
        ])
        (p300, p210, p120, p030, p201,
         unused_p111, p021, p102, p012, p003) = nodes

        self._check(
            nodes, 3,
            np.asfortranarray(np.vstack([p300, p210, p120, p030])),
            np.asfortranarray(np.vstack([p030, p021, p012, p003])),
            np.asfortranarray(np.vstack([p003, p102, p201, p300])))


@utils.needs_surface_speedup
class Test_speedup_compute_edge_nodes(Test__compute_edge_nodes):

    @staticmethod
    def _call_function_under_test(nodes, degree):
        from bezier import _surface_speedup

        return _surface_speedup.compute_edge_nodes(nodes, degree)


class TestIntersectionClassification(unittest.TestCase):

    @utils.needs_surface_speedup
    def test_verify_cython_enums(self):
        from bezier import _surface_helpers
        from bezier import _surface_speedup

        python_enum = _surface_helpers._IntersectionClassification
        cython_enum = _surface_speedup.IntersectionClassification
        self.assertIs(cython_enum, _surface_helpers.IntersectionClassification)

        python_members = python_enum.__members__
        cython_members = cython_enum.__members__
        self.assertEqual(set(python_members), set(cython_members))
        for name, enum_value in six.iteritems(python_members):
            py_value = enum_value.value
            if six.PY3:
                cy_value = cython_members[name].value
            else:  # pragma: NO COVER
                cy_value = cython_members[name]
            self.assertEqual(py_value, cy_value)


def make_intersect(
        first, s, second, t, interior_curve=None,
        index_first=-1, index_second=-1):
    from bezier import _intersection_helpers

    intersection = _intersection_helpers.Intersection(
        first, s, second, t, interior_curve=interior_curve)
    intersection.index_first = index_first
    intersection.index_second = index_second
    return intersection


def get_enum(str_val):
    from bezier import _surface_helpers

    return _surface_helpers.IntersectionClassification[str_val]
