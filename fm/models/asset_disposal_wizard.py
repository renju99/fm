# models/asset_disposal_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class AssetDisposalWizard(models.TransientModel):
    _name = 'facilities.asset.disposal.wizard'
    _description = 'Asset Disposal Wizard'

    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    
    # Disposal Information
    disposal_reason = fields.Selection([
        ('end_of_life', 'End of Life'),
        ('obsolete', 'Obsolete Technology'),
        ('damaged', 'Damaged Beyond Repair'),
        ('replacement', 'Replaced by New Asset'),
        ('cost_ineffective', 'Cost Ineffective'),
        ('safety_concerns', 'Safety Concerns'),
        ('regulatory', 'Regulatory Requirements'),
        ('other', 'Other')
    ], string='Disposal Reason', required=True)
    
    disposal_method = fields.Selection([
        ('sale', 'Sale'),
        ('donation', 'Donation'),
        ('recycling', 'Recycling'),
        ('destruction', 'Destruction'),
        ('trade_in', 'Trade-in'),
        ('auction', 'Auction'),
        ('other', 'Other')
    ], string='Disposal Method', required=True)
    
    disposal_date = fields.Date(string='Disposal Date', default=fields.Date.today, required=True)
    disposal_value = fields.Monetary(string='Disposal Value', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    # Approval Workflow
    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed')
    ], string='Approval State', default='draft')
    
    requested_by_id = fields.Many2one('res.users', string='Requested By', 
                                     default=lambda self: self.env.uid, readonly=True)
    approval_request_date = fields.Datetime(string='Request Date', 
                                          default=fields.Datetime.now, readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Datetime(string='Approval Date', readonly=True)
    approval_notes = fields.Html(string='Approval Notes')
    
    # Disposal Details
    disposal_company = fields.Char(string='Disposal Company', help="Company handling the disposal")
    disposal_contact = fields.Char(string='Disposal Contact', help="Contact person at disposal company")
    disposal_phone = fields.Char(string='Disposal Phone')
    disposal_email = fields.Char(string='Disposal Email')
    
    # Documentation
    disposal_certificate = fields.Binary(string='Disposal Certificate', attachment=True)
    disposal_certificate_filename = fields.Char(string='Certificate Filename')
    disposal_receipt = fields.Binary(string='Disposal Receipt', attachment=True)
    disposal_receipt_filename = fields.Char(string='Receipt Filename')
    
    # Environmental Compliance
    environmental_impact = fields.Selection([
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact')
    ], string='Environmental Impact', default='low')
    
    hazardous_materials = fields.Boolean(string='Contains Hazardous Materials', default=False)
    hazardous_materials_list = fields.Html(string='Hazardous Materials List')
    environmental_compliance_notes = fields.Html(string='Environmental Compliance Notes')
    
    # Financial Impact
    original_value = fields.Monetary(string='Original Value', currency_field='currency_id', 
                                   related='asset_id.purchase_cost', readonly=True)
    current_value = fields.Monetary(string='Current Value', currency_field='currency_id', 
                                  related='asset_id.current_value', readonly=True)
    depreciation_amount = fields.Monetary(string='Total Depreciation', currency_field='currency_id',
                                        compute='_compute_depreciation_amount')
    net_loss_gain = fields.Monetary(string='Net Loss/Gain', currency_field='currency_id',
                                   compute='_compute_net_loss_gain', store=True)
    
    # Notes
    disposal_notes = fields.Html(string='Disposal Notes', help="Additional notes about the disposal process")
    
    @api.depends('original_value', 'current_value')
    def _compute_depreciation_amount(self):
        for wizard in self:
            wizard.depreciation_amount = wizard.original_value - wizard.current_value
    
    @api.depends('disposal_value', 'current_value')
    def _compute_net_loss_gain(self):
        for wizard in self:
            wizard.net_loss_gain = wizard.disposal_value - wizard.current_value
    
    def action_submit_for_approval(self):
        """Submit disposal request for approval"""
        self.ensure_one()
        
        if not self.disposal_reason or not self.disposal_method:
            raise UserError(_("Please fill in all required fields before submitting for approval."))
        
        # Check if asset can be disposed
        if self.asset_id.state == 'disposed':
            raise UserError(_("This asset has already been disposed."))
        
        # Update approval state
        self.write({
            'approval_state': 'pending',
            'approval_request_date': fields.Datetime.now()
        })
        
        # Create approval activity
        self.asset_id.activity_schedule(
            'mail.mail_activity_data_todo',
            note=f"Asset disposal request submitted for {self.asset_id.name}. Reason: {self.disposal_reason}, Method: {self.disposal_method}",
            user_id=self.asset_id.responsible_id.id or self.env.uid
        )
        
        # Send notification to approver
        approver = self._get_approver()
        if approver:
            self.env['mail.channel'].message_post(
                body=f"Asset disposal request for {self.asset_id.name} requires your approval.",
                partner_ids=[approver.partner_id.id]
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Disposal Request Submitted',
                'message': f'Disposal request for {self.asset_id.name} has been submitted for approval',
                'type': 'success'
            }
        }
    
    def action_approve_disposal(self):
        """Approve the disposal request"""
        self.ensure_one()
        
        if self.approval_state != 'pending':
            raise UserError(_("Only pending requests can be approved."))
        
        # Update approval state
        self.write({
            'approval_state': 'approved',
            'approved_by_id': self.env.uid,
            'approval_date': fields.Datetime.now()
        })
        
        # Update asset state
        self.asset_id.write({
            'disposal_workflow_state': 'approved',
            'state': 'disposed'
        })
        
        # Create activity
        self.asset_id.activity_schedule(
            'mail.mail_activity_data_todo',
            note=f"Asset disposal approved for {self.asset_id.name}. Disposal date: {self.disposal_date}",
            user_id=self.env.uid
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Disposal Approved',
                'message': f'Disposal request for {self.asset_id.name} has been approved',
                'type': 'success'
            }
        }
    
    def action_reject_disposal(self):
        """Reject the disposal request"""
        self.ensure_one()
        
        if self.approval_state != 'pending':
            raise UserError(_("Only pending requests can be rejected."))
        
        # Update approval state
        self.write({
            'approval_state': 'rejected',
            'approved_by_id': self.env.uid,
            'approval_date': fields.Datetime.now()
        })
        
        # Reset asset disposal workflow state
        self.asset_id.write({
            'disposal_workflow_state': 'none'
        })
        
        # Create activity
        self.asset_id.activity_schedule(
            'mail.mail_activity_data_todo',
            note=f"Asset disposal rejected for {self.asset_id.name}. Notes: {self.approval_notes or 'No notes provided'}",
            user_id=self.env.uid
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Disposal Rejected',
                'message': f'Disposal request for {self.asset_id.name} has been rejected',
                'type': 'warning'
            }
        }
    
    def action_complete_disposal(self):
        """Complete the disposal process"""
        self.ensure_one()
        
        if self.approval_state != 'approved':
            raise UserError(_("Only approved disposals can be completed."))
        
        # Update approval state
        self.write({
            'approval_state': 'completed'
        })
        
        # Update asset with disposal information
        disposal_vals = {
            'disposal_workflow_state': 'completed',
            'scrap_date': self.disposal_date
        }
        
        # If disposal value is provided, update current value
        if self.disposal_value:
            disposal_vals['current_value'] = self.disposal_value
        
        self.asset_id.write(disposal_vals)
        
        # Create disposal record
        disposal_record = self.env['facilities.asset.disposal'].create({
            'asset_id': self.asset_id.id,
            'disposal_date': self.disposal_date,
            'disposal_reason': self.disposal_reason,
            'disposal_method': self.disposal_method,
            'disposal_value': self.disposal_value,
            'disposal_company': self.disposal_company,
            'environmental_impact': self.environmental_impact,
            'hazardous_materials': self.hazardous_materials,
            'notes': self.disposal_notes
        })
        
        # Create activity
        self.asset_id.activity_schedule(
            'mail.mail_activity_data_todo',
            note=f"Asset disposal completed for {self.asset_id.name}. Disposal value: {self.disposal_value}",
            user_id=self.env.uid
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Disposal Completed',
            'res_model': 'facilities.asset.disposal',
            'view_mode': 'form',
            'res_id': disposal_record.id,
            'target': 'current',
        }
    
    def _get_approver(self):
        """Get the appropriate approver for the disposal"""
        # Logic to determine approver based on asset value, type, etc.
        if self.asset_id.responsible_id and self.asset_id.responsible_id.parent_id:
            return self.asset_id.responsible_id.parent_id.user_id
        elif self.asset_id.responsible_id:
            return self.asset_id.responsible_id.user_id
        else:
            # Default to facility manager or system administrator
            return self.env.ref('base.user_admin')
    
    def action_calculate_disposal_value(self):
        """Calculate estimated disposal value"""
        self.ensure_one()
        
        # Simple calculation based on asset age and condition
        age_factor = 1.0
        if self.asset_id.purchased_date:
            age_days = (fields.Date.today() - self.asset_id.purchased_date).days
            age_years = age_days / 365.25
            age_factor = max(0.1, 1 - (age_years * 0.1))  # 10% depreciation per year
        
        condition_factor = {
            'new': 1.0,
            'good': 0.8,
            'fair': 0.5,
            'poor': 0.2
        }.get(self.asset_id.condition, 0.5)
        
        estimated_value = self.asset_id.purchase_cost * age_factor * condition_factor
        
        self.disposal_value = estimated_value
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Estimated Disposal Value',
                'message': f'Estimated disposal value: {estimated_value:.2f} {self.currency_id.symbol}',
                'type': 'info'
            }
        }


class AssetDisposal(models.Model):
    _name = 'facilities.asset.disposal'
    _description = 'Asset Disposal Records'
    _order = 'disposal_date desc'

    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    disposal_date = fields.Date(string='Disposal Date', required=True)
    disposal_reason = fields.Selection([
        ('end_of_life', 'End of Life'),
        ('obsolete', 'Obsolete Technology'),
        ('damaged', 'Damaged Beyond Repair'),
        ('replacement', 'Replaced by New Asset'),
        ('cost_ineffective', 'Cost Ineffective'),
        ('safety_concerns', 'Safety Concerns'),
        ('regulatory', 'Regulatory Requirements'),
        ('other', 'Other')
    ], string='Disposal Reason', required=True)
    
    disposal_method = fields.Selection([
        ('sale', 'Sale'),
        ('donation', 'Donation'),
        ('recycling', 'Recycling'),
        ('destruction', 'Destruction'),
        ('trade_in', 'Trade-in'),
        ('auction', 'Auction'),
        ('other', 'Other')
    ], string='Disposal Method', required=True)
    
    disposal_value = fields.Monetary(string='Disposal Value', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    disposal_company = fields.Char(string='Disposal Company')
    environmental_impact = fields.Selection([
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact')
    ], string='Environmental Impact')
    
    hazardous_materials = fields.Boolean(string='Contains Hazardous Materials')
    notes = fields.Html(string='Notes')
    
    # Computed fields
    asset_name = fields.Char(string='Asset Name', related='asset_id.name', readonly=True)
    original_value = fields.Monetary(string='Original Value', currency_field='currency_id', 
                                   related='asset_id.purchase_cost', readonly=True)
    net_loss_gain = fields.Monetary(string='Net Loss/Gain', currency_field='currency_id',
                                   compute='_compute_net_loss_gain', store=True)
    
    @api.depends('disposal_value', 'original_value')
    def _compute_net_loss_gain(self):
        for disposal in self:
            disposal.net_loss_gain = disposal.disposal_value - disposal.original_value