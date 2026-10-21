from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Gestion_ot', '0022_material_categoria'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServicioOT',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('cantidad', models.DecimalField(decimal_places=2, max_digits=10)),
                ('precio_unitario', models.DecimalField(decimal_places=2, max_digits=12)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('orden_trabajo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='servicios_facturados',
                    to='Gestion_ot.ordentrabajo',
                )),
            ],
            options={
                'ordering': ['fecha_registro', 'pk'],
            },
        ),
    ]
