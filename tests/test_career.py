import unittest

from horse_racing_game.app.career import career_title, points_for_rank


class CareerTests(unittest.TestCase):
    def test_points_for_rank(self) -> None:
        self.assertEqual(points_for_rank(1), 10)
        self.assertEqual(points_for_rank(2), 7)
        self.assertEqual(points_for_rank(3), 5)
        self.assertEqual(points_for_rank(4), 3)
        self.assertEqual(points_for_rank(5), 1)
        self.assertEqual(points_for_rank(6), 0)

    def test_career_title_reports_progress_and_final_result(self) -> None:
        self.assertEqual(career_title(7, 1), "Career race 2 of 6. 7 points.")
        self.assertEqual(career_title(25, 6), "Champion season complete. 25 points.")
        self.assertEqual(career_title(18, 6), "Strong season complete. 18 points.")
        self.assertEqual(career_title(4, 6), "Rookie season complete. 4 points.")
        self.assertEqual(career_title(7, 1, 3), "Career race 2 of 3. 7 points.")


if __name__ == "__main__":
    unittest.main()
