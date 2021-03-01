from async_search_client.utils.camel import to_camel


def test_camel():
    got = to_camel("this_is_a_test")

    assert got == "thisIsATest"
