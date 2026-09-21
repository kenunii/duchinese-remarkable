"""Strict API schema and deterministic substitution policy."""
# A small, explicit policy rather than accepting any substitution the model calls
# confident. Extend only with visually similar character groups.
CONFUSABLE_GROUPS = ('己已巳', '未末', '土士', '日曰', '乌鸟', '千干', '天夭', '人入')


def obj(properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


def array(items):
    return {'type': 'array', 'items': items}


STRING = {'type': 'string'}
SCHEMA = obj({
    'corrections': array(obj({'offset': {'type': 'integer'}, 'before': STRING,
                              'after': STRING, 'reason': STRING})),
    'sentences': array(obj({
        'translation': STRING,
        'words': array(obj({'text': STRING, 'pinyin': STRING, 'meaning': STRING})),
    })),
})
