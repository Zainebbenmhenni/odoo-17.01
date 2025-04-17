{
    'name': 'Travel Booking',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Travel Search and Booking System',
    'description': """
        Travel booking module with search functionality for flights, accommodations, and more.
    """,
    'depends': ['base', 'website','mass_mailing','contacts','sale_management','mail','website_sale','payment','account','portal'],
    'data': [
        'views/header.xml',
        'security/ir.model.access.csv',
        'data/vol.xml',
        'views/website_templates.xml',
        'views/airport_views.xml',
        'views/form_reservation_avant_pay.xml',
        'views/travel_error.xml',
        'views/result_list_flight.xml',
        'views/bookng_view.xml',
        'views/menu.xml',
        'report/report_booking_ticket.xml',
        'views/payment.xml',
        'views/confirm_reussi.xml',
        'data/annulation_automatique.xml',
        'data/ir_sequence_data.xml',
        'data/sequence.xml',
        'views/ticket.xml',
        'data/action.xml',
        'views/contact.xml',
        'views/booking_dashboard_action.xml',
        'views/userdashboard.xml',
        'views/sign.xml',
        'views/signin.xml',
        'views/welcom.xml',
        'views/acceuil.xml',
        'views/signup_success.xml',
        'views/do_signup.xml',

    ],
    'external_dependencies': {
        'python': ['stripe'],
    },

    'assets': {
        'web.assets_backend': [
            'travel_booking/static/src/js/booking_dashboard.js',
            'travel_booking/static/src/dashboard.xml',
            'travel_booking/static/lib/apexcharts.min.js',
            '/travel_booking/static/src/js/multiple_reservation.js',
        ],
        'web.assets_frontend': [

            'travel_booking/static/src/js/passngers.js',
            'travel_booking/static/src/js/flight_search_loading.js',
            'travel_booking/static/src/js/components/FlightResults.js',
            'travel_booking/static/src/js/flight_results_init.js',
            'travel_booking/static/src/js/resultmulti.js',
        ],

    },
    'installable': True,
    'application': True,
}