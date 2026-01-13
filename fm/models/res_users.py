# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Many2many field for FM groups - computed field that filters user's groups
    # Note: For computed many2many with inverse, we need relation parameters
    fm_groups_ids = fields.Many2many(
        comodel_name='res.groups',
        relation='res_users_fm_groups_rel',
        column1='user_id',
        column2='group_id',
        string='Facilities Management Groups',
        compute='_compute_fm_groups',
        inverse='_inverse_fm_groups',
        store=False,
    )
    
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Override to set domain for fm_groups_ids field"""
        res = super().fields_get(allfields, attributes)
        if 'fm_groups_ids' in res:
            fm_group_ids = self._get_fm_group_ids()
            if fm_group_ids:
                res['fm_groups_ids']['domain'] = [('id', 'in', fm_group_ids)]
            else:
                res['fm_groups_ids']['domain'] = [('id', '=', False)]
        return res

    @api.model
    def _get_fm_group_ids(self):
        """Get list of FM group IDs - cached at model level"""
        if not hasattr(self.env.registry, '_fm_group_ids_cache'):
            fm_group_xmlids = [
                'fm.group_maintenance_technician',
                'fm.group_facilities_user',
                'fm.group_facilities_manager',
                'fm.group_sla_escalation_manager',
                'fm.group_tenant_user',
                'fm.group_facilities_focused_user',
                'fm.group_hide_project_elements',
                'fm.group_facilities_security_admin',
                'fm.group_facilities_security_auditor',
                'fm.group_facilities_high_priority',
            ]
            
            fm_group_ids = []
            for xmlid in fm_group_xmlids:
                try:
                    group = self.env.ref(xmlid, raise_if_not_found=False)
                    if group:
                        fm_group_ids.append(group.id)
                except Exception:
                    pass
            self.env.registry._fm_group_ids_cache = fm_group_ids
        return self.env.registry._fm_group_ids_cache

    @api.model
    def _get_fm_groups_domain(self):
        """Return domain for filtering FM groups - used in views"""
        fm_group_ids = self._get_fm_group_ids()
        return [('id', 'in', fm_group_ids)] if fm_group_ids else [('id', '=', False)]
    
    @api.model
    def _search_fm_groups(self, operator, value):
        """Search domain for FM groups"""
        fm_group_ids = self._get_fm_group_ids()
        if operator == 'in' and value:
            # Filter to only FM groups
            return [('id', 'in', list(set(fm_group_ids) & set(value)))]
        return [('id', 'in', fm_group_ids)]

    def _compute_fm_groups(self):
        """Compute FM-related groups from user's groups - only returns FM groups"""
        fm_group_ids = self._get_fm_group_ids()
        if not fm_group_ids:
            for user in self:
                user.fm_groups_ids = self.env['res.groups']
            return
            
        for user in self:
            # Read from standard relation table and filter to ONLY FM groups
            # This ensures only FM groups are shown
            self.env.cr.execute("""
                SELECT gid FROM res_groups_users_rel 
                WHERE uid = %s AND gid = ANY(%s)
            """, (user.id, fm_group_ids))
            fm_group_ids_found = [row[0] for row in self.env.cr.fetchall()]
            # Only return groups that are in the FM group list
            user.fm_groups_ids = self.env['res.groups'].browse(fm_group_ids_found) if fm_group_ids_found else self.env['res.groups']
            # Ensure we only have FM groups (double check for security)
            user.fm_groups_ids = user.fm_groups_ids.filtered(lambda g: g.id in fm_group_ids)

    def _inverse_fm_groups(self):
        """Update user's groups when fm_groups_ids is changed - only allows FM groups"""
        fm_group_ids = self._get_fm_group_ids()
        if not fm_group_ids:
            return
            
        for user in self:
            # Filter to only allow FM groups (security check)
            valid_fm_groups = user.fm_groups_ids.filtered(lambda g: g.id in fm_group_ids)
            
            # Get all current groups from standard relation table
            self.env.cr.execute("SELECT gid FROM res_groups_users_rel WHERE uid = %s", (user.id,))
            all_group_ids = [row[0] for row in self.env.cr.fetchall()]
            current_groups = self.env['res.groups'].browse(all_group_ids) if all_group_ids else self.env['res.groups']
            
            # Separate FM and non-FM groups
            non_fm_groups = current_groups.filtered(lambda g: g.id not in fm_group_ids)
            
            # Remove old FM groups from standard relation table
            if fm_group_ids:
                self.env.cr.execute("""
                    DELETE FROM res_groups_users_rel 
                    WHERE uid = %s AND gid = ANY(%s)
                """, (user.id, fm_group_ids))
            
            # Add only valid FM groups to standard relation table
            new_fm_group_ids = valid_fm_groups.ids
            if new_fm_group_ids:
                values = [(user.id, gid) for gid in new_fm_group_ids]
                self.env.cr.executemany(
                    "INSERT INTO res_groups_users_rel (uid, gid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    values
                )
            
            # Ensure non-FM groups are still there
            non_fm_group_ids = non_fm_groups.ids
            if non_fm_group_ids:
                values = [(user.id, gid) for gid in non_fm_group_ids]
                self.env.cr.executemany(
                    "INSERT INTO res_groups_users_rel (uid, gid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    values
                )

