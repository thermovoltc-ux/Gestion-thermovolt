from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files import File
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from gestion_mantenimiento.Gestion_ot.storage import GoogleDriveMediaStorage
from gestion_mantenimiento.users.access import obtener_alcance
from gestion_mantenimiento.users.models import Cliente, PerfilUsuario

from . import views
from .models import CentroOperaciones, Equipo, Ubicacion


class ArbolActivosCOFilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='arbol-co-user',
            password='test-password',
        )
        self.group = Group.objects.get_or_create(name='Cliente')[0]
        self.user.groups.add(self.group)
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(
            nombre='Cliente árbol',
            codigo='CLIENTE-ARBOL-CO',
        )
        PerfilUsuario.objects.create(user=self.user, cliente=self.cliente)
        self.centers = {
            codigo: CentroOperaciones.objects.create(
                nombre=f'Centro {codigo}',
                codigo=f'CENTRO-{codigo}-ARBOL',
            )
            for codigo in ('100', '101', '102', '103', '900')
        }
        self.cliente.centros_operaciones.add(*self.centers.values())
        self.root = Ubicacion.objects.create(
            nombre='Planta',
            codigo='PLANTA-CO-TEST',
            co='100',
            centro_operaciones=self.centers['100'],
        )
        self.child = Ubicacion.objects.create(
            nombre='Desposte',
            codigo='DESPOSTE-CO-TEST',
            co='101',
            parent=self.root,
            centro_operaciones=self.centers['101'],
        )
        self.sibling = Ubicacion.objects.create(
            nombre='Empaque',
            codigo='EMPAQUE-CO-TEST',
            co='102',
            parent=self.root,
            centro_operaciones=self.centers['102'],
        )
        self.grandchild = Ubicacion.objects.create(
            nombre='Línea uno',
            codigo='LINEA-CO-TEST',
            co='103',
            parent=self.child,
            centro_operaciones=self.centers['103'],
        )
        self.root_equipo = Equipo.objects.create(
            nombre='Equipo de planta',
            codigo='EQ-PLANTA-CO-TEST',
            ubicacion=self.root,
        )
        self.child_equipo = Equipo.objects.create(
            nombre='Equipo de desposte',
            codigo='EQ-DESPOSTE-CO-TEST',
            ubicacion=self.child,
        )
        session = self.client.session
        session['tipo_cuenta'] = 'administrador'
        session['centro_operaciones_id'] = self.centers['100'].pk
        session.save()

    def _get_nodes(self):
        response = self.client.get(reverse('api_arbol_json'))
        self.assertEqual(response.status_code, 200)
        self.last_scope = obtener_alcance(response.wsgi_request)
        return response.json()['data']

    def test_center_scope_excludes_locations_assigned_to_other_centers(self):
        nodes = self._get_nodes()

        self.assertEqual(self.last_scope.rol, 'administrador')
        self.assertEqual(
            self.last_scope.ubicacion_ids,
            {self.root.pk},
        )
        self.assertEqual([node['id'] for node in nodes], [f'ubicacion-{self.root.pk}'])
        root_node = nodes[0]
        child_nodes = [
            node for node in root_node['children']
            if node['type'] == 'ubicacion'
        ]
        self.assertEqual(child_nodes, [])
        self.assertIn(
            f'equipo-{self.root_equipo.pk}',
            [node['id'] for node in root_node['children']],
        )

    def test_child_center_scope_returns_child_and_its_descendants(self):
        session = self.client.session
        session['centro_operaciones_id'] = self.centers['101'].pk
        session.save()

        nodes = self._get_nodes()

        self.assertEqual([node['id'] for node in nodes], [f'ubicacion-{self.child.pk}'])
        self.assertEqual(nodes[0]['parent'], '#')
        self.assertEqual(
            [node['id'] for node in nodes[0]['children'] if node['type'] == 'ubicacion'],
            [],
        )
        self.assertIn(
            f'equipo-{self.child_equipo.pk}',
            [node['id'] for node in nodes[0]['children']],
        )

    def test_location_page_has_no_manual_co_filter(self):
        response = self.client.get(reverse('lista_activos'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="filtro-co"')

    def test_admin_center_scope_cannot_be_changed_with_query_parameter(self):
        outside = Ubicacion.objects.create(
            nombre='Ubicación externa',
            codigo='OUTSIDE-CO-TEST',
            co='900',
            centro_operaciones=self.centers['900'],
        )

        outside_response = self.client.get(
            reverse('api_arbol_json'),
            {'co': '900'},
        )
        self.assertEqual(outside_response.status_code, 200)
        self.assertEqual(
            [node['id'] for node in outside_response.json()['data']],
            [f'ubicacion-{self.root.pk}'],
        )
        self.assertNotIn(
            f'ubicacion-{outside.pk}',
            [
                node['id']
                for node in outside_response.json()['data'][0]['children']
            ],
        )

    def test_legacy_co_session_remains_supported(self):
        session = self.client.session
        session.pop('centro_operaciones_id', None)
        session['co'] = self.centers['101'].codigo
        session.save()

        nodes = self._get_nodes()

        self.assertEqual([node['id'] for node in nodes], [f'ubicacion-{self.child.pk}'])
        self.assertEqual(nodes[0]['parent'], '#')

    def test_non_admin_cannot_read_tree_roots_or_location_children(self):
        self.user.groups.clear()
        self.user.groups.add(Group.objects.get_or_create(name='Tecnico')[0])
        session = self.client.session
        session['tipo_cuenta'] = 'tecnico'
        session.save()

        roots_response = self.client.get(reverse('api_arbol_json'))
        children_response = self.client.get(
            reverse('api_arbol_json'),
            {'node': f'ubicacion-{self.root.pk}'},
        )

        self.assertEqual(roots_response.status_code, 200)
        self.assertEqual(children_response.status_code, 200)
        self.assertEqual(roots_response.json(), {'data': []})
        self.assertEqual(children_response.json(), {'data': []})

    def test_area_manager_can_read_all_locations_without_co(self):
        outside = Ubicacion.objects.create(
            nombre='Ubicación global',
            codigo='GLOBAL-AREA-MANAGER',
            co='900',
            centro_operaciones=self.centers['900'],
        )
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        session = self.client.session
        session['tipo_cuenta'] = 'jefe_de_area'
        session.pop('centro_operaciones_id', None)
        session.pop('co', None)
        session.save()

        roots_response = self.client.get(reverse('api_arbol_json'))
        children_response = self.client.get(
            reverse('api_arbol_json'),
            {'node': f'ubicacion-{self.root.pk}'},
        )

        self.assertEqual(roots_response.status_code, 200)
        self.assertCountEqual(
            [node['id'] for node in roots_response.json()['data']],
            [f'ubicacion-{self.root.pk}', f'ubicacion-{outside.pk}'],
        )
        self.assertIn(
            f'ubicacion-{self.child.pk}',
            [node['id'] for node in children_response.json()['data']],
        )

    def test_area_manager_with_center_sees_only_that_center(self):
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        session = self.client.session
        session['centro_operaciones_id'] = self.centers['100'].pk
        session.save()

        nodes = self._get_nodes()

        self.assertEqual([node['id'] for node in nodes], [f'ubicacion-{self.root.pk}'])
        self.assertNotIn(f'ubicacion-{self.child.pk}', str(nodes))

    def test_client_can_use_unassociated_center_but_not_other_fk_with_matching_text(self):
        outside = Ubicacion.objects.create(
            nombre='Ubicación fuera del CO',
            codigo='OUTSIDE-CO-CHILDREN',
            co=self.centers['100'].codigo,
            centro_operaciones=self.centers['900'],
        )
        legacy = Ubicacion.objects.create(
            nombre='Ubicación texto CO',
            codigo='LEGACY-TEXT-CO',
            co=self.centers['100'].codigo,
        )

        response = self.client.get(
            reverse('api_arbol_json'),
        )

        self.assertEqual(response.status_code, 200)
        ids = [node['id'] for node in response.json()['data']]
        self.assertIn(f'ubicacion-{legacy.pk}', ids)
        self.assertNotIn(f'ubicacion-{outside.pk}', ids)

    def test_client_scope_uses_center_without_client_association(self):
        other_cliente = Cliente.objects.create(
            nombre='Otro cliente',
            codigo='OTRO-CLIENTE-ARBOL',
        )
        unauthorized_center = CentroOperaciones.objects.create(
            nombre='No autorizado',
            codigo='CENTRO-NO-AUTORIZADO',
        )
        other_cliente.centros_operaciones.add(unauthorized_center)
        unauthorized_location = Ubicacion.objects.create(
            nombre='Ubicación no autorizada',
            codigo='UBI-NO-AUTORIZADA',
            co='100',
            centro_operaciones=unauthorized_center,
        )
        session = self.client.session
        session['centro_operaciones_id'] = unauthorized_center.pk
        session['co'] = '100'
        session.save()

        nodes = self._get_nodes()
        self.assertEqual([node['id'] for node in nodes], [f'ubicacion-{unauthorized_location.pk}'])

    def test_malformed_center_session_does_not_fall_back_to_legacy_co(self):
        session = self.client.session
        session['centro_operaciones_id'] = 'invalid'
        session['co'] = '100'
        session.save()

        self.assertEqual(self._get_nodes(), [])


class CentroOperacionesEndpointIsolationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cliente-activos-scope',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.client.force_login(self.user)
        self.allowed_center = CentroOperaciones.objects.create(
            nombre='CO permitido',
            codigo='CO-ACTIVOS-PERMITIDO',
        )
        self.other_center = CentroOperaciones.objects.create(
            nombre='CO ajeno',
            codigo='CO-ACTIVOS-AJENO',
        )
        self.allowed_location = Ubicacion.objects.create(
            nombre='Ubicación permitida',
            codigo='UBI-ACTIVOS-PERMITIDA',
            centro_operaciones=self.allowed_center,
        )
        self.foreign_location = Ubicacion.objects.create(
            nombre='Ubicación privada ajena',
            codigo='UBI-ACTIVOS-AJENA',
            centro_operaciones=self.other_center,
        )
        self.allowed_equipment = Equipo.objects.create(
            nombre='Equipo permitido',
            codigo='EQ-ACTIVOS-PERMITIDO',
            ubicacion=self.allowed_location,
        )
        self.foreign_equipment = Equipo.objects.create(
            nombre='Equipo privado ajeno',
            codigo='EQ-ACTIVOS-AJENO',
            ubicacion=self.foreign_location,
        )
        session = self.client.session
        session['centro_operaciones_id'] = self.allowed_center.pk
        session['tipo_cuenta'] = 'jefe_de_area'
        session.save()

    def test_asset_list_only_returns_selected_center(self):
        response = self.client.get(reverse('lista_activos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.allowed_location.nombre)
        self.assertNotContains(response, self.foreign_location.nombre)
        self.assertEqual(
            list(response.context['ubicaciones_all']),
            [self.allowed_location],
        )

    def test_direct_foreign_location_and_equipment_crud_is_not_accessible(self):
        responses = [
            self.client.get(
                reverse('editar_ubicacion', args=[self.foreign_location.pk]),
            ),
            self.client.post(
                reverse('eliminar_ubicacion', args=[self.foreign_location.pk]),
            ),
            self.client.get(
                reverse('editar_equipo', args=[self.foreign_equipment.pk]),
            ),
            self.client.post(
                reverse('eliminar_equipo', args=[self.foreign_equipment.pk]),
            ),
        ]

        self.assertTrue(all(response.status_code == 404 for response in responses))
        self.assertTrue(
            Ubicacion.objects.filter(pk=self.foreign_location.pk).exists(),
        )
        self.assertTrue(
            Equipo.objects.filter(pk=self.foreign_equipment.pk).exists(),
        )

    def test_foreign_equipment_pdf_and_location_zip_are_not_accessible(self):
        pdf_response = self.client.get(
            reverse('hoja_vida_equipo', args=[self.foreign_equipment.pk]),
        )
        zip_response = self.client.get(
            reverse(
                'descargar_hojas_vida_ubicacion',
                args=[self.foreign_location.pk],
            ),
        )

        self.assertEqual(pdf_response.status_code, 404)
        self.assertEqual(zip_response.status_code, 404)

    def test_client_without_center_has_empty_asset_scope_even_if_session_role_is_internal(self):
        session = self.client.session
        session.pop('centro_operaciones_id', None)
        session['tipo_cuenta'] = 'jefe_de_area'
        session.save()

        tree_response = self.client.get(reverse('api_arbol_json'))
        list_response = self.client.get(reverse('lista_activos'))
        create_response = self.client.get(reverse('crear_ubicacion'))
        edit_location_response = self.client.get(
            reverse('editar_ubicacion', args=[self.allowed_location.pk]),
        )
        edit_equipment_response = self.client.get(
            reverse('editar_equipo', args=[self.allowed_equipment.pk]),
        )
        pdf_response = self.client.get(
            reverse('hoja_vida_equipo', args=[self.allowed_equipment.pk]),
        )
        zip_response = self.client.get(
            reverse(
                'descargar_hojas_vida_ubicacion',
                args=[self.allowed_location.pk],
            ),
        )

        self.assertEqual(tree_response.json(), {'data': []})
        self.assertEqual(list(list_response.context['ubicaciones_all']), [])
        self.assertEqual(create_response.status_code, 404)
        self.assertEqual(edit_location_response.status_code, 404)
        self.assertEqual(edit_equipment_response.status_code, 404)
        self.assertEqual(pdf_response.status_code, 404)
        self.assertEqual(zip_response.status_code, 404)


class CentroOperacionesModelTests(TestCase):
    def test_cliente_can_share_and_have_multiple_operation_centers(self):
        cliente_one = Cliente.objects.create(nombre='Cliente uno', codigo='CLIENTE-CO-001')
        cliente_two = Cliente.objects.create(nombre='Cliente dos', codigo='CLIENTE-CO-002')
        centro_uno = CentroOperaciones.objects.create(
            nombre='Planta',
            codigo='CO-PLANTA',
        )
        centro_dos = CentroOperaciones.objects.create(
            nombre='Punto de venta',
            codigo='CO-PDV',
        )

        cliente_one.centros_operaciones.add(centro_uno, centro_dos)
        cliente_two.centros_operaciones.add(centro_uno)
        ubicacion = Ubicacion.objects.create(
            nombre='Ubicación de planta',
            codigo='UBI-CO-PLANTA',
            centro_operaciones=centro_uno,
        )

        self.assertSetEqual(
            set(cliente_one.centros_operaciones.all()),
            {centro_uno, centro_dos},
        )
        self.assertSetEqual(
            set(centro_uno.clientes.all()),
            {cliente_one, cliente_two},
        )
        self.assertEqual(ubicacion.centro_operaciones, centro_uno)
        self.assertEqual(str(centro_uno), 'CO-PLANTA - Planta')


class AssetDriveMediaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='asset-drive-user',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Admin')[0])
        self.location = Ubicacion.objects.create(
            nombre='Ubicación con foto Drive',
            codigo='UBI-ASSET-DRIVE',
        )
        self.equipment = Equipo.objects.create(
            nombre='Equipo con foto Drive',
            codigo='EQ-ASSET-DRIVE',
            ubicacion=self.location,
        )

    def _set_drive_image(self, instance, field_name, file_id):
        image_field = getattr(instance, field_name)
        image_field.name = f'drive/{file_id}/file.png'
        instance.save(update_fields=[field_name])

    def test_asset_image_fields_use_google_drive_storage(self):
        self.assertIsInstance(
            Ubicacion._meta.get_field('imagen').storage,
            GoogleDriveMediaStorage,
        )
        self.assertIsInstance(
            Equipo._meta.get_field('imagen').storage,
            GoogleDriveMediaStorage,
        )

    def test_hoja_vida_image_resolver_reads_from_equipment_field_storage(self):
        self._set_drive_image(self.equipment, 'imagen', 'equipment-pdf-image')
        image_name = self.equipment.imagen.name

        with patch(
            'gestion_mantenimiento.Gestion_ot.storage.GoogleDriveMediaStorage.open',
            side_effect=lambda *args: File(
                BytesIO(b'pdf-equipment-image'),
                name='file.png',
            ),
        ) as open_image:
            image_bytes = views._resolve_equipo_image_bytes(self.equipment)

        self.assertEqual(image_bytes, b'pdf-equipment-image')
        open_image.assert_called_once_with(image_name, 'rb')

    def test_hoja_vida_image_resolver_logs_if_configured_image_is_unreadable(self):
        self._set_drive_image(self.equipment, 'imagen', 'unreadable-equipment-image')

        with patch(
            'gestion_mantenimiento.Gestion_ot.storage.GoogleDriveMediaStorage.open',
            side_effect=OSError('Drive unavailable'),
        ):
            with patch.object(
                views.default_storage,
                'open',
                side_effect=OSError('No local image'),
            ):
                with patch.object(views.logger, 'warning') as log_warning:
                    image_bytes = views._resolve_equipo_image_bytes(self.equipment)

        self.assertIsNone(image_bytes)
        log_warning.assert_called_once()

    def test_drive_media_serves_location_and_equipment_images_to_tree_users(self):
        self._set_drive_image(self.location, 'imagen', 'location-image-id')
        self._set_drive_image(self.equipment, 'imagen', 'equipment-image-id')
        self.client.force_login(self.user)

        with patch(
            'gestion_mantenimiento.Gestion_ot.views.GoogleDriveMediaStorage.open',
            side_effect=lambda *args: File(
                BytesIO(b'asset-image'),
                name='file.png',
            ),
        ) as open_image:
            for file_id in ('location-image-id', 'equipment-image-id'):
                with self.subTest(file_id=file_id):
                    response = self.client.get(
                        reverse('drive_media', args=[file_id]),
                    )

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response['Content-Type'], 'image/png')
                    self.assertEqual(response['Cache-Control'], 'private, no-store')
                    self.assertEqual(
                        b''.join(response.streaming_content),
                        b'asset-image',
                    )

        self.assertEqual(open_image.call_count, 2)

    def test_admin_can_only_view_asset_images_inside_center_scope(self):
        self._set_drive_image(self.location, 'imagen', 'allowed-location-image')
        unauthorized_center = CentroOperaciones.objects.create(
            nombre='Centro no autorizado',
            codigo='ASSET-DRIVE-OUTSIDE',
        )
        unauthorized_location = Ubicacion.objects.create(
            nombre='Ubicación fuera de alcance',
            codigo='UBI-ASSET-OUTSIDE',
            centro_operaciones=unauthorized_center,
        )
        self._set_drive_image(
            unauthorized_location,
            'imagen',
            'outside-location-image',
        )

        cliente = Cliente.objects.create(
            nombre='Cliente de alcance Drive',
            codigo='CLIENTE-ASSET-DRIVE',
        )
        center = CentroOperaciones.objects.create(
            nombre='Centro permitido',
            codigo='ASSET-DRIVE-ALLOWED',
        )
        cliente.centros_operaciones.add(center)
        self.location.centro_operaciones = center
        self.location.save(update_fields=['centro_operaciones'])
        PerfilUsuario.objects.create(user=self.user, cliente=cliente)
        self.user.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.client.force_login(self.user)
        session = self.client.session
        session['tipo_cuenta'] = 'administrador'
        session['centro_operaciones_id'] = center.pk
        session.save()

        with patch(
            'gestion_mantenimiento.Gestion_ot.views.GoogleDriveMediaStorage.open',
            side_effect=lambda *args: File(
                BytesIO(b'allowed-image'),
                name='file.png',
            ),
        ) as open_image:
            allowed_response = self.client.get(
                reverse('drive_media', args=['allowed-location-image']),
            )
            self.assertEqual(allowed_response.status_code, 200)
            self.assertEqual(
                b''.join(allowed_response.streaming_content),
                b'allowed-image',
            )

            denied_response = self.client.get(
                reverse('drive_media', args=['outside-location-image']),
            )
            self.assertEqual(denied_response.status_code, 404)

        self.assertEqual(open_image.call_count, 1)
