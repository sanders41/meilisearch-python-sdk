# Pydantic usage

This package uses [Pydantic](https://pydantic-docs.helpmanual.io/) to serialize/deserialize the JSON
from MeiliSearch into Python objects wherever possible, and in the process converts the camelCaseNames
from JSON into more Pythonic snake_case_names.

In some instances it is not possible to return the data as an object because the structure will be
dependant on your particular dataset and can't be known ahead of time. In these instances you can
either work with the data in the dictionary that is returned, or because you will know the structure
you can generate your own Pydantic models.

As an example, if you want to get a movie from the [small movies example](https://github.com/sanders41/meilisearch-python-async/blob/main/datasets/small_movies.json)
you could put the results into an object with the following:

```py
from datetime import datetime
from typing import Optional

from meilisearch_python_async import Client
from meilisearch_python_async.models import CamelBase


# Inheriting from CamelBase will allow your class to automatically convert
# variables returned from the server in camelCase into snake_case. It will
# also make it a Pydantic Model.
class Movie(CamelBase):
    id: int
    title: str
    poster: str
    overview: str
    release_date: datetime
    genre: Optional[str] = None


async with Client("http://127.0.0.1:7700", "masterKey") as client:
    index = client.index("movies")
    movie_dict = await index.get_document(287947)
    movie = Movie(**movie_dict)
```

And then the movie variable would contain the movie object with the following information

```py
Movie(
    id = 287947,
    title = "Shazam!",
    poster = "https://image.tmdb.org/t/p/w1280/xnopI5Xtky18MPhK40cZAGAOVeV.jpg",
    overview = "A boy is given the ability to become an adult superhero in times of need with a single magic word.",
    release_date = datetime.datetime(2019, 3, 23, 0, 0, tzinfo=datetime.timezone.utc),
    genre = "action",
)
```

By inheriting from CamelBase, or any of the other [provided models](https://github.com/sanders41/meilisearch-python-async/tree/main/meilisearch_python_async/models)
you will be inheriting Pydantic models and therefore have access to the funcitonality Pydantic provides
such as [validators](https://pydantic-docs.helpmanual.io/usage/validators/) and [Fields](https://pydantic-docs.helpmanual.io/usage/model_config/#alias-precedence).
Pydantic will also automatically deserialized the data into the correct data type based on the type
hint provided.
