# Generated by Django 5.2 on 2025-04-30 03:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_empresa_options_alter_empresa_actualizado_por_and_more'),
        ('gestion', '0007_cliente_tags_proveedor_tags'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='cliente',
            options={'ordering': ['empresa__razon_social', 'nombre'], 'verbose_name': 'Cliente', 'verbose_name_plural': 'Clientes'},
        ),
        migrations.AlterModelOptions(
            name='cobro',
            options={'ordering': ['empresa__razon_social', '-fecha_factura', 'numero_documento'], 'verbose_name': 'Registro de Cobro', 'verbose_name_plural': 'Registros de Cobros'},
        ),
        migrations.AlterModelOptions(
            name='cuentabancaria',
            options={'ordering': ['empresa__razon_social', 'nombre_banco', 'numero_cuenta'], 'verbose_name': 'Cuenta Bancaria', 'verbose_name_plural': 'Cuentas Bancarias'},
        ),
        migrations.AlterModelOptions(
            name='gastorecurrente',
            options={'ordering': ['empresa__razon_social', 'grupo_concepto', 'descripcion'], 'verbose_name': 'Gasto Recurrente (Plantilla)', 'verbose_name_plural': 'Gastos Recurrentes (Plantillas)'},
        ),
        migrations.AlterModelOptions(
            name='pago',
            options={'ordering': ['empresa__razon_social', '-fecha_vencimiento_inicial', 'fecha_emision_factura'], 'verbose_name': 'Registro de Pago a Proveedor', 'verbose_name_plural': 'Registros de Pagos a Proveedores'},
        ),
        migrations.AlterModelOptions(
            name='proveedor',
            options={'ordering': ['empresa__razon_social', 'nombre'], 'verbose_name': 'Proveedor', 'verbose_name_plural': 'Proveedores'},
        ),
        migrations.AlterModelOptions(
            name='ventaproyectada',
            options={'ordering': ['empresa__razon_social', 'fecha_cierre_estimada', 'estatus'], 'verbose_name': 'Venta Proyectada / Oportunidad', 'verbose_name_plural': 'Ventas Proyectadas / Oportunidades'},
        ),
        migrations.AddField(
            model_name='cliente',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='clientes', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='cobro',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cobros', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='cobro',
            name='moneda',
            field=models.CharField(default='USD', help_text='Moneda de esta factura específica (ej: USD, EUR)', max_length=3, verbose_name='Moneda Transacción (ISO 4217)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='cuentabancaria',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cuentasbancarias', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='gastorecurrente',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='gastosrecurrentes', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='pago',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pagos', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='pago',
            name='moneda',
            field=models.CharField(default='USD', help_text='Moneda de esta factura específica (ej: USD, EUR)', max_length=3, verbose_name='Moneda Transacción (ISO 4217)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='proveedor',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='proveedores', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='ventaproyectada',
            name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ventasproyectadas', to='core.empresa', verbose_name='Empresa'),
        ),
        migrations.AddField(
            model_name='ventaproyectada',
            name='moneda',
            field=models.CharField(default='USD', max_length=3, verbose_name='Moneda Venta Proyectada'),
        ),
        migrations.AlterField(
            model_name='cuentabancaria',
            name='moneda',
            field=models.CharField(default='USD', max_length=3, verbose_name='Moneda Cuenta'),
        ),
        migrations.AlterField(
            model_name='gastorecurrente',
            name='moneda',
            field=models.CharField(default='USD', max_length=3, verbose_name='Moneda'),
        ),
        migrations.AlterUniqueTogether(
            name='cliente',
            unique_together={('empresa', 'identificacion')},
        ),
        migrations.AlterUniqueTogether(
            name='cuentabancaria',
            unique_together={('empresa', 'numero_cuenta')},
        ),
        migrations.AlterUniqueTogether(
            name='proveedor',
            unique_together={('empresa', 'identificacion')},
        ),
    ]
