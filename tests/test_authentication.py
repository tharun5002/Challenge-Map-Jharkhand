import hashlib
import unittest

from authentication import (
    LEGACY_PASSWORD_ITERATIONS,
    hash_password,
    password_needs_rehash,
    validate_new_account,
    verify_password,
)


class AuthenticationTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verifiable(self):
        password = "a-unique-long-passphrase"
        first_salt, first_hash = hash_password(password)
        second_salt, second_hash = hash_password(password)

        # Argon2id embeds its own random salt in the PHC string, so two hashes
        # of the same password differ even though the scheme marker does not.
        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password(password, first_salt, first_hash))
        self.assertTrue(verify_password(password, second_salt, second_hash))
        self.assertFalse(verify_password("incorrect-password", first_salt, first_hash))

    def test_registration_validation(self):
        username = validate_new_account(
            "  citizen_1  ",
            "a-long-citizen-password",
            "a-long-citizen-password",
        )
        self.assertEqual(username, "citizen_1")

        invalid_accounts = [
            ("ab", "a-long-citizen-password", "a-long-citizen-password"),
            ("invalid name", "a-long-citizen-password", "a-long-citizen-password"),
            ("citizen", "short", "short"),
            ("citizen", "a-long-citizen-password", "different-password"),
        ]
        for username, password, confirmation in invalid_accounts:
            with self.subTest(username=username, password=password):
                with self.assertRaises(ValueError):
                    validate_new_account(username, password, confirmation)

    def test_malformed_hash_data_fails_closed(self):
        self.assertFalse(verify_password("password", "not-hex", "not-hex"))
        self.assertFalse(verify_password("password", "not-hex", "$argon2id$broken"))

    def test_new_hashes_are_argon2id(self):
        salt, hashed = hash_password("a-unique-long-passphrase")

        self.assertEqual(salt, "argon2id")
        self.assertTrue(hashed.startswith("$argon2id$v=19$"))
        self.assertFalse(password_needs_rehash(hashed))

    def test_legacy_pbkdf2_rows_still_verify_and_are_rehashed(self):
        salt = b"0123456789abcdef"
        legacy_hash = hashlib.pbkdf2_hmac(
            "sha256", b"legacy-passphrase", salt, LEGACY_PASSWORD_ITERATIONS
        ).hex()

        self.assertTrue(
            verify_password("legacy-passphrase", salt.hex(), legacy_hash)
        )
        self.assertFalse(verify_password("wrong-passphrase", salt.hex(), legacy_hash))
        self.assertTrue(password_needs_rehash(legacy_hash))


if __name__ == "__main__":
    unittest.main()
