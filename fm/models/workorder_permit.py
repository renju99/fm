from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

class MaintenanceWorkorderPermit(models.Model):
    _name = 'facilities.workorder.permit'
    _description = 'Work Order Permit'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Permit Name", required=True, tracking=True)
    permit_type = fields.Selection([
        ('electrical', 'Electrical'),
        ('mechanical', 'Mechanical'),
        ('hotwork', 'Hot Work'),
        ('confined', 'Confined Space'),
        ('general', 'General'),
    ], string="Permit Type", required=True, tracking=True)
    workorder_id = fields.Many2one('facilities.workorder', string="Work Order", required=True, ondelete='cascade', tracking=True)
    issued_date = fields.Date(string="Issued Date", tracking=True)
    expiry_date = fields.Date(string="Expiry Date", tracking=True)
    status = fields.Selection([
        ('requested', 'Requested'),
        ('pending_manager_approval', 'Pending Manager Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ], string="Status", default='requested', required=True, tracking=True)
    notes = fields.Html(string="Notes")
    requested_by_id = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user, tracking=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By", tracking=True)
    rejected_reason = fields.Html(string="Rejection Reason", tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    facility_manager_id = fields.Many2one(
        'res.users',
        string="Facility Manager",
        compute='_compute_facility_manager',
        store=False,
        help="The user account of the facility manager. This field is computed based on the facility assigned to the work order's asset."
    )

    @api.depends('workorder_id')
    def _compute_facility_manager(self):
        for permit in self:
            manager = False
            if permit.workorder_id and permit.workorder_id.asset_id and permit.workorder_id.asset_id.facility_id:
                facility = permit.workorder_id.asset_id.facility_id
                manager = facility.manager_id
                if manager and hasattr(manager, 'user_id') and manager.user_id:
                    permit.facility_manager_id = manager.user_id
                elif manager and manager._name == 'res.users':
                    permit.facility_manager_id = manager
                else:
                    permit.facility_manager_id = False
            else:
                permit.facility_manager_id = False

    def get_facility_manager_status(self):
        """Get detailed information about the facility manager status for debugging."""
        self.ensure_one()
        if not self.workorder_id or not self.workorder_id.asset_id or not self.workorder_id.asset_id.facility_id:
            return {
                'status': 'error',
                'message': 'No facility associated with this permit',
                'details': 'The work order must have an asset assigned to a facility.'
            }
        
        facility = self.workorder_id.asset_id.facility_id
        if not facility.manager_id:
            return {
                'status': 'error',
                'message': 'No facility manager assigned',
                'details': f'Facility "{facility.name}" does not have a manager assigned.',
                'facility_name': facility.name,
                'facility_id': facility.id
            }
        
        manager = facility.manager_id
        if not manager.user_id:
            return {
                'status': 'error',
                'message': 'Facility manager has no user account',
                'details': f'Facility manager "{manager.name}" does not have a user account assigned.',
                'facility_name': facility.name,
                'facility_id': facility.id,
                'manager_name': manager.name,
                'manager_id': manager.id
            }
        
        return {
            'status': 'success',
            'message': 'Facility manager is properly configured',
            'details': f'Facility manager "{manager.name}" has user account "{manager.user_id.name}".',
            'facility_name': facility.name,
            'facility_id': facility.id,
            'manager_name': manager.name,
            'manager_id': manager.id,
            'user_name': manager.user_id.name,
            'user_id': manager.user_id.id
        }

    def action_submit_for_approval(self):
        for permit in self:
            if permit.status != 'requested':
                raise UserError(_("Permit is not in 'Requested' stage!"))
            
            # Check if we have a facility manager assigned
            if not permit.workorder_id or not permit.workorder_id.asset_id or not permit.workorder_id.asset_id.facility_id:
                raise UserError(_("This permit is not associated with a facility. Please ensure the work order has an asset assigned to a facility."))
            
            facility = permit.workorder_id.asset_id.facility_id
            if not facility.manager_id:
                raise UserError(_("No facility manager is assigned to facility '%s'. Please assign a facility manager first.") % facility.name)
            
            if not facility.manager_id.user_id:
                raise UserError(_("Facility manager '%s' for facility '%s' does not have a user account. Please ensure the facility manager has a user account assigned.") % (facility.manager_id.name, facility.name))
            
            manager_user = permit.facility_manager_id
            if not manager_user:
                raise UserError(_("Unable to determine facility manager user for this permit. Please check the facility manager assignment."))
            
            permit.status = 'pending_manager_approval'
            # Create scheduled activity for the manager
            activity_type = self.env.ref('mail.mail_activity_data_todo')
            model_id = self.env['ir.model']._get_id('facilities.workorder.permit')
            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id,
                'res_id': permit.id,
                'res_model_id': model_id,
                'user_id': manager_user.id,
                'summary': _("Permit Approval Required"),
                'note': _("Please approve permit '%s' for work order '%s'.") % (permit.name, permit.workorder_id.name),
                'date_deadline': fields.Date.today(),
            })
            permit.message_post(body=_("Approval request sent to Facility Manager: %s" % manager_user.name),
                                partner_ids=[manager_user.partner_id.id])

    def action_approve(self):
        for permit in self:
            manager_user = permit.facility_manager_id
            if permit.status != 'pending_manager_approval':
                raise UserError(_("Permit is not awaiting manager approval."))
            if manager_user and self.env.user == manager_user:
                permit.status = 'approved'
                permit.approved_by_id = self.env.user.id
                permit.issued_date = fields.Date.today()  # Set issued date to approval date
                permit.message_post(body=_("Permit approved by Facility Manager."))
            else:
                raise UserError(_("Only the facility manager of this facility can approve this permit."))

    def action_reject(self):
        for permit in self:
            manager_user = permit.facility_manager_id
            if permit.status != 'pending_manager_approval':
                raise UserError(_("Permit is not awaiting manager approval."))
            if manager_user and self.env.user == manager_user:
                # Require rejection reason
                if not permit.rejected_reason:
                    raise UserError(_("Please provide a rejection reason before rejecting the permit."))
                permit.status = 'rejected'
                permit.message_post(body=_("Permit rejected by Facility Manager. Reason: %s" % permit.rejected_reason))
            else:
                raise UserError(_("Only the facility manager of this facility can reject this permit."))

    def cron_remind_expiring_permits(self):
        """Send reminders and create activities for permits expiring soon."""
        today = fields.Date.today()
        threshold = today + timedelta(days=7)
        expiring_permits = self.search([
            ('expiry_date', '!=', False),
            ('status', 'in', ['approved']),
            ('expiry_date', '<=', threshold)
        ])
        for permit in expiring_permits:
            # Notify the facility manager
            manager_user = permit.facility_manager_id
            if manager_user:
                # Create scheduled activity for manager
                activity_type = self.env.ref('mail.mail_activity_data_todo')
                model_id = self.env['ir.model']._get_id('facilities.workorder.permit')
                self.env['mail.activity'].create({
                    'activity_type_id': activity_type.id,
                    'res_id': permit.id,
                    'res_model_id': model_id,
                    'user_id': manager_user.id,
                    'summary': _("Permit Expiry Reminder"),
                    'note': _("Permit '%s' for Work Order '%s' is expiring on %s. Please take necessary action.") % (
                        permit.name, permit.workorder_id.name, permit.expiry_date),
                    'date_deadline': permit.expiry_date,
                })
                permit.message_post(body=_("Reminder: Permit is expiring soon (%s)." % permit.expiry_date),
                                    partner_ids=[manager_user.partner_id.id])