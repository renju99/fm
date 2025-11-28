# -*- coding: utf-8 -*-

from odoo import http

class TestController(http.Controller):

    @http.route('/test-route', type='http', auth='public')
    def test_route(self, **kwargs):
        """Simple test route"""
        return "<h1>Test Controller Working!</h1><p>This proves controllers are loading.</p>"
