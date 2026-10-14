import pytest
from star.desktop_core import Settings

def test_image_routing_defaults_on_and_prompt_addition_off():
    assert Settings().media_chat_auto is True
    assert Settings().session_capabilities_prompt is False

@pytest.mark.parametrize('field', ['media_chat_auto','session_capabilities_prompt'])
def test_image_settings_require_bool(field):
    settings = Settings()
    setattr(settings, field, 'yes')
    with pytest.raises(ValueError, match='Tool access settings'):
        settings.validate()
