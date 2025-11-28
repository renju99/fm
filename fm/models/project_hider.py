# -*- coding: utf-8 -*-
from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)


class ProjectHider(models.TransientModel):
    _name = 'facilities.project.hider'
    _description = 'Hide Project Module Elements'

    @api.model
    def hide_project_elements(self):
        """
        Hide project-related UI elements to keep facilities management clean.
        This method can be called via cron or manually.
        """
        try:
            # Hide main project menu items
            project_menus = [
                'project.menu_main_pm',
                'project.menu_project_root', 
                'project.menu_project_config',
            ]
            
            for menu_xmlid in project_menus:
                try:
                    menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
                    if menu:
                        menu.active = False
                        _logger.info(f"Hidden menu: {menu_xmlid}")
                except Exception as e:
                    _logger.warning(f"Could not hide menu {menu_xmlid}: {str(e)}")
            
            # Hide project actions
            project_actions = [
                'project.project_project_action',
                'project.action_view_task',
                'project.action_view_all_task',
            ]
            
            for action_xmlid in project_actions:
                try:
                    action = self.env.ref(action_xmlid, raise_if_not_found=False)
                    if action:
                        action.active = False
                        _logger.info(f"Hidden action: {action_xmlid}")
                except Exception as e:
                    _logger.warning(f"Could not hide action {action_xmlid}: {str(e)}")
            
            # Move project modules to hidden category
            hidden_category = self.env.ref('base.module_category_hidden', raise_if_not_found=False)
            if hidden_category:
                project_modules = self.env['ir.module.module'].search([
                    ('name', 'in', ['project', 'project_account', 'project_stock', 'website_project', 'project_todo'])
                ])
                
                for module in project_modules:
                    module.write({
                        'application': False,
                        'category_id': hidden_category.id
                    })
                    _logger.info(f"Hidden module: {module.name}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Project Elements Hidden'),
                    'message': _('Project module elements have been hidden from the UI'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error hiding project elements: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Could not hide all project elements: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def show_project_elements(self):
        """
        Show project elements if needed for debugging or if user wants them back.
        """
        try:
            # Show main project menu items
            project_menus = [
                'project.menu_main_pm',
                'project.menu_project_root',
                'project.menu_project_config',
            ]
            
            for menu_xmlid in project_menus:
                try:
                    menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
                    if menu:
                        menu.active = True
                        _logger.info(f"Shown menu: {menu_xmlid}")
                except Exception as e:
                    _logger.warning(f"Could not show menu {menu_xmlid}: {str(e)}")
            
            # Show project actions
            project_actions = [
                'project.project_project_action',
                'project.action_view_task',
                'project.action_view_all_task',
            ]
            
            for action_xmlid in project_actions:
                try:
                    action = self.env.ref(action_xmlid, raise_if_not_found=False)
                    if action:
                        action.active = True
                        _logger.info(f"Shown action: {action_xmlid}")
                except Exception as e:
                    _logger.warning(f"Could not show action {action_xmlid}: {str(e)}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Project Elements Restored'),
                    'message': _('Project module elements have been restored to the UI'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error showing project elements: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Could not show all project elements: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
