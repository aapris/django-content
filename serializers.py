from rest_framework import serializers
from rest_framework.reverse import reverse

from content.models import Content, Videoinstance


class VideoinstanceSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        request = self.context.get("request")
        url = reverse("instance", kwargs={"uid": obj.content.uid, "extension": obj.extension}, request=request)
        return url

    class Meta:
        model = Videoinstance
        fields = ["url", "mimetype", "filesize", "duration", "bitrate", "width", "height", "framerate", "created"]


class ContentSerializer(serializers.HyperlinkedModelSerializer):
    original_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    videoinstances = VideoinstanceSerializer(many=True, read_only=True)

    def get_original_url(self, obj):
        request = self.context.get("request")
        url = reverse("original", kwargs={"uid": obj.uid, "filename": obj.originalfilename}, request=request)
        return url

    def get_preview_url(self, obj: Content):
        request = self.context.get("request")
        if obj.preview:
            url = reverse(
                "preview",
                kwargs={"uid": obj.uid, "width": "W", "height": "H", "action": "", "ext": "jpg"},
                request=request,
            )
        else:
            url = None
        return url

    class Meta:
        model = Content
        fields = [
            "uid",
            "title",
            "caption",
            "author",
            "original_url",
            "preview_url",
            "videoinstances",
            "originalfilename",
            "filesize",
            "filetime",
            "sha1",
            "point",
            "mimetype",
            "created",
            "updated",
        ]

    def create(self, validated_data):
        """
        Create a new Content instance.
        Note that lots of saving process is done in views.py and models.py.
        """
        c = Content(**validated_data)
        c.save()
        return c
