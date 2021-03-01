def to_camel(snake_string: str) -> str:
    """
    Converts a camelCaseString into a snake_case_string
    """
    words = snake_string.split("_")

    return words[0] + "".join(word.title() for word in words[1:])
