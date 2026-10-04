# Hand-written migration. ``makemigrations`` refuses to emit this one because
# turning the nullable ``Movie.cover`` of 0001 into a required field needs a
# one-off default, and that question is interactive (it dies with EOFError in
# CI/scripts). The data step below is the explicit answer: NULL -> '' first, then
# the NOT NULL rebuild, then the two indexes 0001 never created.

from django.db import migrations, models


def replace_missing_covers(apps, schema_editor):
    """Turn NULL covers into '' so the NOT NULL rebuild has nothing to copy.

    Must run before the AlterField below: on SQLite the nullability change is a
    table rebuild, and a surviving NULL would violate the new constraint.
    """
    Movie = apps.get_model('movies', 'Movie')
    Movie.objects.using(schema_editor.connection.alias).filter(cover__isnull=True).update(cover='')


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            replace_missing_covers,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='movie',
            name='cover',
            field=models.ImageField(max_length=500, upload_to='movie_covers/', verbose_name='imagen de portada'),
        ),
        migrations.AddIndex(
            model_name='movie',
            index=models.Index(fields=['title'], name='movies_movie_title_idx'),
        ),
        migrations.AddIndex(
            model_name='rating',
            index=models.Index(fields=['movie'], name='movies_rating_movie_idx'),
        ),
    ]
