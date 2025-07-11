

# run from awx-manage shell


from django.apps import apps

# List all models that have `pending_deletion` field
models = [model for model in apps.get_models() if hasattr(model, 'pending_deletion')]

for model in models:
    pending = model.objects.filter(pending_deletion=True)
    if pending.exists():
        print(f"Model: {model.__name__}")
        for obj in pending:
            print(f"  ID: {obj.id}, Name: {getattr(obj, 'name', '(no name)')}")
