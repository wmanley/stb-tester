# Run with ./run-tests.sh

test_that_stbt_config_reads_from_STBT_CONFIG_FILE() {
    [ "$(stbt-config global.test_key)" = "this is a test value" ]
}

test_that_stbt_config_searches_in_specified_section() {
    [ "$(stbt-config special.test_key)" = "not the global value" ]
}

test_that_stbt_config_reads_from_stbt_repo_stbt_conf() {
    printf "[repo_test]\nkey=value\n" >stbt.conf &&
    [ "$(stbt-config repo_test.key)" = "value" ] &&

    mkdir subdir &&
    cd subdir &&
    [ "$(stbt-config repo_test.key)" = "value" ]
}

test_that_stbt_config_returns_failure_on_key_not_found() {
    ! stbt-config global.no_such_key &&
    ! stbt-config no_such_section.test_key &&
    ! stbt-config not_special.section
}
