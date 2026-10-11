import pytest
from star.desktop_core import Settings


def test_chat_images_on_by_default():
    assert Settings().media_chat_auto is True


def test_chat_images_setting_rejects_non_bool():
    settings = Settings(media_chat_auto='yes')
    with pytest.raises(ValueError, match='Tool access settings'):
        settings.validate()
