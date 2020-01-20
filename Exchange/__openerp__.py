# -*- coding: utf-8 -*-
{
    'name': "Exchange",

    'summary': """
        Exchange shipping items.
    """,
    'description': """
        Exchange shipping items.
    """,

    'author': "Giorgi Khetaguri",

    'category': 'Warehouse Management',
    'version': '0.1',

    'depends': ['base', 'stock', 'sale'],

    'data': [
        # 'security/ir.model.access.csv',
        'templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}