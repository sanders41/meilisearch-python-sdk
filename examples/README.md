# Meilisearch Python SDK Examples

To run the examples create and activate a virtual environment inside the `examples` directory
then install the requirements.

```sh
pip install -r requirements.txt
```

Start a Meilisearch running on locally with a master key set to `masterKey`. Then you can run
the example files, i.e.:

```sh
python add_documents_decorator.py
```

## FastAPI Example

To run the FastAPI example run

```sh
fastapi dev fastapi_example.py
```

Then go to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to test the routes.
