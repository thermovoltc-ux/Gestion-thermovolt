import argparse
import csv
import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / 'gestion_mantenimiento'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_mantenimiento.settings')

import django

django.setup()

from django.db import transaction
from gestion_mantenimiento.Gestion_ot.models import Material


CATEGORY_CODES = {
    'R': 'repuestos',
    'M': 'maquinaria',
    'F': 'frio',
    'L': 'locativos',
    'S': 'servicios',
}
SALE_MARGIN_FACTOR = Decimal('0.7')


def parse_cost(value):
    cleaned = value.strip().replace('$', '').replace(' ', '')
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        cents = cleaned.rsplit(',', 1)[-1]
        if len(cents) == 2:
            whole, _, cents = cleaned.rpartition(',')
            cleaned = whole.replace(',', '').replace('.', '') + '.' + cents
        else:
            cleaned = cleaned.replace(',', '').replace('.', '')
    try:
        return Decimal(cleaned).quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ValueError(f'Costo no válido: {value!r}') from exc


def load_rows(csv_path):
    with csv_path.open('r', encoding='utf-8-sig', newline='') as catalog_file:
        reader = csv.DictReader(catalog_file)
        expected = {'categoria', 'nombre', 'costo_base'}
        if not reader.fieldnames or not expected.issubset(
            {field.strip().lower() for field in reader.fieldnames}
        ):
            raise ValueError(
                'El CSV debe tener las columnas categoria,nombre,costo_base.'
            )

        field_names = {field.strip().lower(): field for field in reader.fieldnames}
        for line_number, row in enumerate(reader, start=2):
            category_code = row[field_names['categoria']].strip().upper()
            category = CATEGORY_CODES.get(category_code)
            source_code = (row.get(field_names.get('codigo', ''), '') or '').strip()
            name = row[field_names['nombre']].strip()
            if not category:
                raise ValueError(
                    f'Línea {line_number}: categoría desconocida {category_code!r}. '
                    'Usa R, M, F, L o S.'
                )
            if not name:
                raise ValueError(f'Línea {line_number}: falta el nombre.')

            cost = parse_cost(row[field_names['costo_base']])
            if cost < 0:
                raise ValueError(f'Línea {line_number}: el costo no puede ser negativo.')
            yield line_number, category, source_code, name, cost


def import_catalog(csv_path, dry_run=False):
    counts = {category: {'created': 0, 'updated': 0} for category in CATEGORY_CODES.values()}

    with transaction.atomic():
        for line_number, category, source_code, name, cost in load_rows(csv_path):
            if source_code:
                material = Material.objects.filter(codigo=source_code).first()
            else:
                material = Material.objects.filter(
                    categoria=category,
                    nombre__iexact=name,
                ).order_by('pk').first()
            suggested_sale_price = (cost / SALE_MARGIN_FACTOR).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            )

            if material is None:
                material = Material(
                    codigo=source_code,
                    categoria=category,
                    nombre=name,
                    costo_base=cost,
                    precio_venta_sugerido=suggested_sale_price,
                )
                if not dry_run:
                    material.save()
                counts[category]['created'] += 1
            else:
                material.categoria = category
                material.nombre = name
                material.costo_base = cost
                material.precio_venta_sugerido = suggested_sale_price
                if not dry_run:
                    material.save(update_fields=[
                        'categoria',
                        'nombre',
                        'costo_base',
                        'precio_venta_sugerido',
                    ])
                counts[category]['updated'] += 1

    labels = {
        'repuestos': 'Repuestos',
        'maquinaria': 'Maquinaria',
        'frio': 'Frío',
        'locativos': 'Locativos',
        'servicios': 'Servicios',
    }
    for category, result in counts.items():
        print(
            f"{labels[category]}: {result['created']} nuevos, "
            f"{result['updated']} actualizados"
        )


def main():
    parser = argparse.ArgumentParser(
        description='Importa el catálogo CSV sin modificar el costo base indicado.'
    )
    parser.add_argument(
        'csv_path',
        nargs='?',
        type=Path,
        default=PROJECT_DIR / 'catalogo.csv',
        help='CSV con columnas categoria,nombre,costo_base y codigo opcional.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Valida y cuenta los registros sin guardar cambios.',
    )
    args = parser.parse_args()
    if not args.csv_path.is_file():
        parser.error(f'No existe el archivo de catálogo: {args.csv_path}')
    import_catalog(args.csv_path, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
