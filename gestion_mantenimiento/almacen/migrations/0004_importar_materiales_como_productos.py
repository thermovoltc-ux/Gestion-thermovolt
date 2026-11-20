from django.db import migrations


def forwards(apps, schema_editor):
    Material = apps.get_model('Gestion_ot', 'Material')
    CategoriaProducto = apps.get_model('almacen', 'CategoriaProducto')
    Producto = apps.get_model('almacen', 'Producto')
    database = schema_editor.connection.alias

    categoria = None
    productos = Producto.objects.using(database)
    creados = 0

    for material in Material.objects.using(database).order_by('pk').iterator(
        chunk_size=500,
    ):
        if productos.filter(material_asociado_id=material.pk).exists():
            continue

        codigo = (material.codigo or '').strip()
        if not codigo or productos.filter(codigo=codigo).exists():
            codigo = f'MAT-{material.pk}'
            sufijo = 1
            while productos.filter(codigo=codigo).exists():
                codigo = f'MAT-{material.pk}-{sufijo}'
                sufijo += 1

        if categoria is None:
            categoria, _ = CategoriaProducto.objects.using(database).get_or_create(
                nombre='Repuestos',
                defaults={
                    'descripcion': (
                        'Productos importados del catálogo de materiales.'
                    ),
                },
            )

        productos.create(
            codigo=codigo,
            nombre=material.nombre,
            categoria_id=categoria.pk,
            unidad_medida='Unidad',
            stock_minimo=0,
            material_asociado_id=material.pk,
        )
        creados += 1

    print(f'Productos creados desde materiales: {creados}')


def backwards(apps, schema_editor):
    # Mantener los productos importados evita perder inventario o movimientos posteriores.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('Gestion_ot', '0028_materialot_codigo_snapshot_and_more'),
        ('almacen', '0003_herramientaunidad_historialherramienta_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
