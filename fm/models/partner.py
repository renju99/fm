# models/partner.py
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Tenant identification
    is_tenant = fields.Boolean(string='Is Tenant', default=False, tracking=True,
                              help="Check this if the partner is a tenant")
    tenant_type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('government', 'Government Entity'),
    ], string='Tenant Type', help="Type of tenant")
    tenant_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('blacklisted', 'Blacklisted'),
    ], string='Tenant Status', default='active', help="Current status of the tenant")
    resident_id_number = fields.Char(string="Resident ID Number", 
                                   help="Government issued ID number")
    license_number = fields.Char(string="License Number",
                                help="Business license number (if company)")
    licensing_authority = fields.Char(string="Licensing Authority",
                                    help="Authority that issued the license")
    
    # Landlord identification  
    is_landlord = fields.Boolean(string='Is Landlord', default=False, tracking=True,
                                help="Check this if the partner is a landlord")
    landlord_type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('trust', 'Trust'),
        ('government', 'Government Entity'),
    ], string='Landlord Type', help="Type of landlord")
    
    # Relationships
    lease_ids = fields.One2many('facilities.lease', 'tenant_partner_id', 
                               string='Leases as Tenant')
    landlord_lease_ids = fields.One2many('facilities.lease', 'landlord_partner_id',
                                        string='Leases as Landlord')
    facility_ids = fields.One2many('facilities.facility', 'landlord_partner_id',
                                  string='Facility List')
    tenant_facility_ids = fields.One2many('facilities.facility', 'tenant_partner_id',
                                         string='Rented Facility List')
    
    # Statistics
    active_leases_count = fields.Integer(string='Active Leases', 
                                        compute='_compute_lease_counts', store=True)
    total_leases_count = fields.Integer(string='Total Leases',
                                       compute='_compute_lease_counts', store=True)
    owned_facilities_count = fields.Integer(string='Owned Facilities',
                                           compute='_compute_facility_counts', store=True)
    rented_facilities_count = fields.Integer(string='Rented Facilities', 
                                            compute='_compute_facility_counts', store=True)

    @api.depends('lease_ids', 'lease_ids.state')
    def _compute_lease_counts(self):
        for partner in self:
            partner.total_leases_count = len(partner.lease_ids)
            partner.active_leases_count = len(partner.lease_ids.filtered(
                lambda l: l.state == 'active'))

    @api.depends('facility_ids', 'tenant_facility_ids')
    def _compute_facility_counts(self):
        for partner in self:
            partner.owned_facilities_count = len(partner.facility_ids)
            partner.rented_facilities_count = len(partner.tenant_facility_ids)

    @api.onchange('is_tenant')
    def _onchange_is_tenant(self):
        if not self.is_tenant:
            self.tenant_type = False
            self.tenant_status = 'active'

    @api.onchange('is_landlord') 
    def _onchange_is_landlord(self):
        if not self.is_landlord:
            self.landlord_type = False
