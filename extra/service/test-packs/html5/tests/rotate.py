from stbt import press, wait_for_match


def test_that_image_is_rotated_by_arrows():
    press("KEY_LEFT")
    wait_for_match('stb-tester-left.png')
    press("KEY_RIGHT")
    wait_for_match('stb-tester-right.png')
    press("KEY_UP")
    wait_for_match('stb-tester-up.png')
    press("KEY_DOWN")
    wait_for_match('stb-tester-down.png')


def test_that_image_returns_to_normal_on_OK():
    press("KEY_OK")
    wait_for_match('stb-tester-350px.png')


def test_that_custom_key_is_recognised():
    press("KEY_CUSTOM")
    wait_for_match('stb-tester-up.png')

if __name__ == '__main__':
    test_that_image_is_rotated_by_arrows()
    test_that_image_returns_to_normal_on_OK()
    test_that_custom_key_is_recognised()
