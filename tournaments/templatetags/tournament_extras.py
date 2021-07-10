from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def select(iter_of_objects, key):
    for obj in iter_of_objects:
        if isinstance(obj, dict):
            yield obj[key]
        else:
            yield getattr(obj, key)


@register.filter("sum")
def sum_filter(iter_of_numbers):
    return sum(float(f) for f in iter_of_numbers)


@register.filter
def div(numerator, denominator):
    return float(numerator) / float(denominator)


@register.filter
def split(value, separator=","):
    return value.split(separator)


@register.filter
def model_filter(query, clause):
    unpacked = [i.strip() for i in clause.split("=", maxsplit=1)]
    if len(unpacked) != 2:
        raise ValueError(
            f"Invalid filter format.  Expected 'field=value', got instead: {clause!r}"
        )
    return query.filter(**{unpacked[0]: unpacked[1]})
