"""Physical acceptance checks. Diagnostic entry events are never view health."""
import math


def integer(value):
    return not isinstance(value, bool) and isinstance(value,(int,float)) and math.isfinite(value) and value==int(value)


def validate(value, nonce, previous=None, key=None, expected_index=None):
    if value.get('schema') != 2 or value.get('nonce') != nonce:
        raise ValueError('Wrong view health identity/schema')
    for name in ('sequence','keyEvents','lastKey','focusIndex'):
        if not integer(value.get(name)) or value[name] < 0:
            raise ValueError('Invalid view counter: '+name)
    if value['focusIndex'] > 10 or not value.get('rootSource','').startswith('file:///tmp/YSM/'):
        raise ValueError('Unexpected view source/index')
    for name in ('moduleResolved','componentInstantiated','initialized','windowAttached',
                 'nativeContextAttached','ready','shown','visible','activeFocus'):
        if value.get(name) is not True: raise ValueError('View is not accepted: '+name)
    if value.get('originalFallback') is not False: raise ValueError('Original fallback is active')
    if previous is not None:
        if value['sequence'] <= previous['sequence']: raise ValueError('Stale view heartbeat')
        if value['keyEvents'] < previous['keyEvents']: raise ValueError('Input counter decreased')
    if key is not None:
        if previous is None or value['keyEvents'] <= previous['keyEvents'] or value['lastKey'] != key or value['focusIndex'] != expected_index:
            raise ValueError('Genuine input did not change the expected selected item')
    return value
