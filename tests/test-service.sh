#!/bin/bash

service_dir=$testdir/../extra/service

trap_add()
{
    trap_add_cmd=$1; shift || fatal "${FUNCNAME} usage error"
    for trap_add_name in "$@"; do
        trap -- "$(
            # helper fn to get existing trap command from output
            # of trap -p
            extract_trap_cmd() { printf '%s\n' "$3"; }
            # print existing trap command with newline
            eval "extract_trap_cmd $(trap -p "${trap_add_name}")"
            # print the new trap command
            printf '%s\n' "${trap_add_cmd}"
        )" "${trap_add_name}" \
            || fatal "unable to add to trap ${trap_add_name}"
    done
}

serve_test_packs()
{
    test_pack="$scratchdir/test-packs" &&
    mkdir -p "$test_pack" &&
    for pack in $testdir/../extra/service/test-packs/*/;
    do
        cd $test_pack &&
        git init test-pack-wd 1>&2 &&
        cd test-pack-wd &&
        cp -R "$pack"/* .  1>&2 &&
        git add .  1>&2 &&
        git commit -m "Initial Commit"  1>&2 &&
        cd .. &&
        git clone --bare test-pack-wd $(basename $pack).git &&
        touch $(basename $pack).git/git-daemon-export-ok &&
        rm -rf test-pack-wd
    done &&
    git daemon --reuseaddr --pid-file=pid-file --detach --base-path=$test_pack \
               $test_pack 1>&2 &&
    ls -l "$test_pack" 1>&2 &&
    echo "GIT_DAEMON_PID=$(cat pid-file)" &&
    echo "TEST_PACKS_GIT_URL=git://172.17.42.1" &&
    echo "TEST_PACK_DIR=$test_pack"
}

start_service()
{
    rid="$(basename $scratchdir)"

    if [ -e "$scratchdir/stbt.conf" ]; then
        extra_args="-v $scratchdir/stbt.conf:/etc/stbt/stbt.conf:ro"
    fi

    mkdir -p "$scratchdir/.ssh/"
    ssh-keygen -f "$scratchdir/.ssh/id_rsa" -N "" >/dev/null 2>&1
    eval $(ssh-agent -s) >/dev/null 2>&1
    ssh-add "$scratchdir/.ssh/id_rsa" >/dev/null 2>&1

    docker run --name="stbt-service-credentials-$rid" \
        stbtester/stb-tester-service-credentials &&
    docker run -i --rm --volumes-from=stbt-service-credentials-$rid ubuntu:14.04 \
        tee /etc/stbt/users/test-user.pub <$scratchdir/.ssh/id_rsa.pub &&
    docker run --name="stbt-service-results-$rid" \
        stbtester/stb-tester-service-results &&
    SERVICE_CID="$(docker run -d -p 22 -v /etc/localtime:/etc/localtime:ro \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --volumes-from=stbt-service-credentials-$rid \
        --volumes-from=stbt-service-results-$rid \
        --name=stbt-service-$rid \
        $extra_args \
        stbtester/stb-tester-service)" &&
    SERVICE_HOSTNAME=$(
        docker inspect --format '{{ .NetworkSettings.IPAddress }}' $SERVICE_CID)

    trap_add stop_service EXIT
    while ! nc -z "$SERVICE_HOSTNAME" 22; do
        echo "Awaiting service startup on $SERVICE_HOSTNAME"
        sleep 0.5
    done
    ssh-keygen -R "$SERVICE_HOSTNAME" || true
    ssh -T -o "StrictHostKeyChecking no" stb-tester@$SERVICE_HOSTNAME \
        >/dev/null 2>&1 || true
}

stop_service()
{
    ssh-keygen -R "$SERVICE_HOSTNAME"
    docker kill "$SERVICE_CID"
    docker wait "$SERVICE_CID"
    docker rm "$SERVICE_CID" "stbt-service-results-$rid" "stbt-service-credentials-$rid"
}

stop_test_pack()
{
    kill $GIT_DAEMON_PID &&
    rm -Rf $TEST_PACK_DIR
}

service_test_setup()
{
    [ -z "$ENABLE_DOCKER_TESTS" ] && exit 77
    export $(serve_test_packs 2>/dev/null) &&
    trap stop_test_pack EXIT &&
    start_service 2>/dev/null || fail "Service setup failed"
}

build_virtual_stb()
{
    tar -C $testdir/../extra/virtual-stb/examples/$1 -c . \
        | ssh stb-tester@$SERVICE_HOSTNAME \
          stbt-ssh-endpoint build-virtual-stb $2 - \
    || fail "Test setup failed"
}

test_service_with_virtual_stb()
{
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service &&
    tar -C $testdir/../extra/virtual-stb/examples/html5 -c . \
        | ssh stb-tester@$SERVICE_HOSTNAME \
          stbt-ssh-endpoint build-virtual-stb virtual-stb:test-service - &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh
}

test_service_with_videotestsrc()
{
    service_test_setup &&

    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git ./run.sh
}

test_that_failure_building_virtual_stb_is_propogated_back_through_ssh()
{
    service_test_setup &&

    mkdir bad-test-pack &&
    printf "FROM ubuntu:14.04\nRUN false" >bad-test-pack/Dockerfile &&
    ! tar -C bad-test-pack -c Dockerfile | ssh stb-tester@$SERVICE_HOSTNAME \
        stbt-ssh-endpoint build-virtual-stb virtual-stb:test-service -
}

test_that_failing_test_propogates_back_through_ssh()
{
    service_test_setup &&

    ! ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git false
}

test_that_stdout_comes_purely_from_the_test_pack()
{
    service_test_setup &&

    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git \
        echo "This is a test" >output &&
    diff -u <(echo "This is a test") output
}

test_that_stdout_comes_purely_from_the_test_pack_with_virtual_stb()
{
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git \
        echo "This is a test" >output &&
    diff -u <(echo "This is a test") output
}

test_that_we_can_run_tests_from_the_same_repo_twice()
{
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh
}

test_that_we_can_run_tests_from_different_repos()
{
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git ./run.sh
}

test_that_we_can_run_tests_from_different_repos_concurrently()
{
    set -x &&
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service \
    || fail "Test setup failed"

    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh &
    html5_test_pid=$! &&

    # The results directories are named according to their timestamp with a
    # precision of 1 second.  Ensure that there is no time clash until this
    # issue is resolved.  These tests should still overlap.
    sleep 2

    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git ./run.sh &&
    wait $html5_test_pid
}

test_that_later_versions_of_virtual_stb_override_earlier_ones()
{
    service_test_setup &&

    tar -C $testdir/../extra/virtual-stb/examples/html5 -c . \
        | tar --delete ./virtual-stb/stb-tester-350px.png \
        | ssh stb-tester@$SERVICE_HOSTNAME \
          stbt-ssh-endpoint build-virtual-stb virtual-stb:test-service - &&
    ! ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh \
    || fail "Broken virtual-stb image tests should fail"

    tar -C $testdir/../extra/virtual-stb/examples/html5 -c . \
        | ssh stb-tester@$SERVICE_HOSTNAME \
          stbt-ssh-endpoint build-virtual-stb virtual-stb:test-service - &&
    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --with-virtual-stb=virtual-stb:test-service \
        --test-pack-url=$TEST_PACKS_GIT_URL/html5.git ./run.sh \
    || fail "Old image is being used"
}

test_that_we_cant_run_concurrent_tests_against_configured_hardware()
{
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service \
    || fail "Test setup failed"

    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git ./run.sh &
    test_1_pid=$!

    ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
        --test-pack-url=$TEST_PACKS_GIT_URL/videotestsrc.git ./run.sh
    test_2_result=$?

    # One should succeed, one should fail
    if wait "$test_1_pid"; then
        [ "$test_2_result" != 0 ] || fail "Both tests succeeded"
    else
        [ "$test_2_result" = 0 ] || fail "Both tests failed"
    fi
}

test_that_updates_to_a_test_pack_are_detected_in_subseqeuent_runs()
{
    service_test_setup &&

    git clone $TEST_PACK_DIR/html5 &&
    cd html5 &&
    touch new_file &&
    git add new_file &&
    origoldsha=$(git rev-parse HEAD) &&
    git commit -m "New file" &&
    orignewsha=$(git rev-parse HEAD) &&
    git config --global push.default simple &&
    [ "$origoldsha" != "$orignewsha" ] || fail "Test Setup Error"

    oldsha=$(ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
             --test-pack-url=$TEST_PACKS_GIT_URL/html5.git \
             git rev-parse HEAD) &&

    git push &&
    newsha=$(ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
             --test-pack-url=$TEST_PACKS_GIT_URL/html5.git \
             git rev-parse HEAD) \
    || fail "Test failure"

    [ "$origoldsha" = "$oldsha" ] || fail "Old SHA doesn't match"
    [ "$orignewsha" = "$newsha" ] || fail "Updated SHA doesn't match"
}

test_running_test_pack_by_sha()
{
    service_test_setup &&
    sha=$(git -C "$TEST_PACK_DIR/html5.git" rev-parse --verify HEAD) &&
    remotesha=$(ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
                --test-pack-url=$TEST_PACKS_GIT_URL/html5.git \
                --test-pack-revision=$sha \
                git rev-parse HEAD) \
    || fail "Test error"

    [ "$sha" = "$remotesha" ] || fail "SHAs don't match"
}

test_that_config_from_host_ends_up_in_test_pack()
{
    printf '[global]\ntest=moo' >$scratchdir/stbt.conf &&
    service_test_setup &&
    global_test="$(ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
             --test-pack-url=$TEST_PACKS_GIT_URL/html5.git \
             stbt config global.test)"
    [ "$global_test" = "moo" ] || fail "Config is not preserved"
}

test_that_virtual_stb_ip_address_is_set_in_config()
{
    service_test_setup &&

    build_virtual_stb html5 virtual-stb:test-service &&

    address="$(ssh -T "stb-tester@$SERVICE_HOSTNAME" stbt-ssh-endpoint run \
             --test-pack-url=$TEST_PACKS_GIT_URL/html5.git \
             --with-virtual-stb=virtual-stb:test-service \
             stbt config device_under_test.address)"

    [[ "$address" =~ [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+ ]] \
        || fail "IP Address '$address' is not correct"
}
