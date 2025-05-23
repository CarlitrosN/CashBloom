# Generated by Django 5.2 on 2025-04-27 02:15

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion', '0003_cuentabancaria_ventaproyectada'),
    ]

    operations = [
        migrations.AddField(
            model_name='cobro',
            name='adjunto_factura',
            field=models.FileField(blank=True, null=True, upload_to='facturas_cobros/', verbose_name='Adjunto (Factura/Doc)'),
        ),
        migrations.AddField(
            model_name='cobro',
            name='venta_proyectada_origen',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cobros_generados', to='gestion.ventaproyectada', verbose_name='Venta Proyectada Origen'),
        ),
        migrations.AddField(
            model_name='pago',
            name='adjunto_documento',
            field=models.FileField(blank=True, null=True, upload_to='facturas_pagos/', verbose_name='Adjunto (Factura/Doc)'),
        ),
        migrations.AlterField(
            model_name='cobro',
            name='numero_cuotas',
            field=models.PositiveSmallIntegerField(default=1, help_text='Máximo 12. Las cuotas se generarán automáticamente al guardar.', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)], verbose_name='Número de Cuotas'),
        ),
        migrations.AlterField(
            model_name='pago',
            name='numero_cuotas',
            field=models.PositiveSmallIntegerField(default=1, help_text='Máximo 12. Las cuotas se generarán automáticamente al guardar.', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)], verbose_name='Número de Cuotas a Pagar'),
        ),
    ]
