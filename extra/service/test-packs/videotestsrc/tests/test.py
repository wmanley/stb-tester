from stbt import wait_for_match


def test_videotestsrc():
    wait_for_match("videotestsrc-redblue.png", consecutive_matches=2)

if __name__ == '__main__':
    test_videotestsrc()
