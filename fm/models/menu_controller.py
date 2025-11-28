# -*- coding: utf-8 -*-

from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class MenuController(models.Model):
    """Custom menu controller to handle facilities management menu visibility"""
    _name = 'facilities.menu.controller'
    _description = 'Facilities Management Menu Controller'

    @api.model
    def get_facilities_menu_visibility(self):
        """Check if user has access to facilities management features"""
        user = self.env.user
        
        # Check if user has any facilities management groups
        facilities_groups = self.env['res.groups'].search([
            ('name', 'ilike', 'facilities'),
            ('users', 'in', [user.id])
        ])
        
        has_facilities_access = len(facilities_groups) > 0
        
        _logger.info(f"User {user.name} has facilities access: {has_facilities_access}")
        _logger.info(f"User groups: {[g.name for g in user.groups_id]}")
        
        return {
            'has_facilities_access': has_facilities_access,
            'facilities_groups': [g.name for g in facilities_groups]
        }

    @api.model
    def check_menu_access(self, menu_name):
        """Check if user has access to specific menu"""
        user = self.env.user
        
        # Define menu access rules
        menu_access_rules = {
            'facilities': ['Facilities Management User', 'Facilities Management Manager', 'Facilities Technician'],
            'asset_management': ['Facilities Management User', 'Facilities Management Manager', 'Facilities Technician'],
            'maintenance': ['Facilities Management User', 'Facilities Management Manager', 'Facilities Technician'],
            'space_booking': ['Facilities Management User', 'Facilities Management Manager', 'Facilities Technician', 'Tenant User'],
            'analytics': ['Facilities Management User', 'Facilities Management Manager'],
            'financial_management': ['Facilities Management Manager'],
            'vendor_management': ['Facilities Management User', 'Facilities Management Manager'],
            'safety_management': ['Facilities Management User', 'Facilities Management Manager'],
            'energy_management': ['Facilities Management User', 'Facilities Management Manager']
        }
        
        if menu_name not in menu_access_rules:
            return True  # Allow access to unknown menus
            
        required_groups = menu_access_rules[menu_name]
        user_groups = [g.name for g in user.groups_id]
        
        # Check if user has any of the required groups
        has_access = any(group in user_groups for group in required_groups)
        
        _logger.info(f"Menu '{menu_name}' access for user {user.name}: {has_access}")
        _logger.info(f"Required groups: {required_groups}")
        _logger.info(f"User groups: {user_groups}")
        
        return has_access
