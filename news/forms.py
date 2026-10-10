from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Article, ArticleTag, Tag, UserProfile


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Correo electrónico')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')


class ArticleForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple, label='Etiquetas',
    )

    class Meta:
        model = Article
        fields = ('title', 'slug', 'summary', 'body', 'featured_image', 'categories')
        widgets = {'body': forms.Textarea(attrs={'rows': 12})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['tags'].initial = self.instance.tags.all()
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def save(self, commit=True):
        article = super().save(commit=commit)
        selected_tags = self.cleaned_data['tags']
        if commit:
            selected_ids = {tag.pk for tag in selected_tags}
            ArticleTag.objects.filter(article=article).exclude(tag_id__in=selected_ids).delete()
            for index, tag in enumerate(selected_tags):
                ArticleTag.objects.update_or_create(
                    article=article, tag=tag, defaults={'position': index},
                )
        return article


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('display_name', 'biography')
        widgets = {'biography': forms.Textarea(attrs={'rows': 5})}
