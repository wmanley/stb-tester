# Run with ./run-tests.sh

validate_stbt_repo() {
    [ -e README ] &&
    [ -e log ] &&
    [ -e stbt.conf ] || fail "Files missing from stbt repo"

    # git repo exists and is pristine:
    [ "$(git rev-parse --show-toplevel)" = "$PWD" ] &&
    [ "$(git status --porcelain)" = "" ] || fail "stbt repo in bad state"

    # tests repo exists and is pristine:
    [ -e test-scripts ] &&
    cd test-scripts &&
    [ -e tests ] &&
    [ -e library ] &&
    [ -e README ] &&
    [ "$(git rev-parse --show-toplevel)" = "$PWD" ] &&
    [ "$(git status --porcelain)" = "" ] || fail "tests repo in bad state"

    # If tests repo has an upstream it should match that in stbt config
    [ "$(stbt-config service.test_scripts_repo)" \
        = "$(git config remote.origin.url)" ] || fail "Upstream tests url incorrect"

    cd ..
}

create_test_test_repo() {
    mkdir upstream-tests &&
    cd upstream-tests &&
    git init --quiet &&
    mkdir tests library &&
    touch tests/.gitignore library/.gitignore &&
    echo 'Upstream!' > README &&
    git add README tests/.gitignore library/.gitignore &&
    git commit --quiet -m "Upstream repo created" &&
    echo $PWD || fail "Test setup failed: couldn't create upstream repo"
}

test_stbt_init_in_empty_dir() {
    mkdir empty &&
    cd empty &&
    stbt-init &&
    validate_stbt_repo
}

test_stbt_init_with_upstream_tests_repo() {
    upstream=$(create_test_test_repo) &&
    mkdir stbtdir &&
    cd stbtdir &&
    stbt-init --test-scripts-repo "$upstream" &&
    validate_stbt_repo &&
    [ "$(<test-scripts/README)" = "Upstream!" ]
}
