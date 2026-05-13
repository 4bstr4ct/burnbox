from burnbox.account import _generate_password, _PASSWORD_LEN, _MIN_PASSWORD_LEN


class TestGeneratePassword:
    def test_default_length(self):
        pw = _generate_password()
        assert len(pw) == _PASSWORD_LEN

    def test_has_lowercase(self):
        pw = _generate_password()
        assert any(c.islower() for c in pw)

    def test_has_uppercase(self):
        pw = _generate_password()
        assert any(c.isupper() for c in pw)

    def test_has_digit(self):
        pw = _generate_password()
        assert any(c.isdigit() for c in pw)

    def test_has_special(self):
        pw = _generate_password()
        assert any(c in "!@#$%&*" for c in pw)

    def test_custom_length(self):
        pw = _generate_password(20)
        assert len(pw) == 20

    def test_minimum_length(self):
        pw = _generate_password(8)
        assert len(pw) == 8

    def test_too_short_raises(self):
        try:
            _generate_password(7)
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_unique_across_calls(self):
        pw1 = _generate_password()
        pw2 = _generate_password()
        assert pw1 != pw2
