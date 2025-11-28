# models/asset_threshold.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AssetThreshold(models.Model):
    _name = 'facilities.asset.threshold'
    _description = 'Asset Condition Thresholds'
    _order = 'name'

    name = fields.Char(string='Threshold Name', required=True)
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True, ondelete='cascade')
    
    # Threshold Configuration
    threshold_type = fields.Selection([
        ('runtime_hours', 'Runtime Hours'),
        ('maintenance_count', 'Maintenance Count'),
        ('cost_threshold', 'Cost Threshold'),
        ('age_threshold', 'Age Threshold'),
        ('utilization', 'Utilization Rate'),
        ('custom', 'Custom Condition')
    ], string='Threshold Type', required=True)
    
    # Condition Parameters
    condition_operator = fields.Selection([
        ('>', 'Greater Than'),
        ('>=', 'Greater Than or Equal'),
        ('<', 'Less Than'),
        ('<=', 'Less Than or Equal'),
        ('==', 'Equal To'),
        ('!=', 'Not Equal To')
    ], string='Condition Operator', required=True, default='>')
    
    threshold_value = fields.Float(string='Threshold Value', required=True)
    unit = fields.Char(string='Unit', help="Unit of measurement")
    
    # Action Configuration
    action_type = fields.Selection([
        ('create_workorder', 'Create Work Order'),
        ('send_alert', 'Send Alert'),
        ('update_status', 'Update Asset Status'),
        ('schedule_maintenance', 'Schedule Maintenance'),
        ('escalate', 'Escalate to Manager')
    ], string='Action Type', required=True, default='send_alert')
    
    # Work Order Configuration
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection')
    ], string='Work Order Type', default='corrective')
    
    work_order_priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High')
    ], string='Work Order Priority', default='2')
    
    # Alert Configuration
    alert_message = fields.Html(string='Alert Message',
                           help="Custom message to send when threshold is exceeded")
    alert_recipients = fields.Many2many('res.users', string='Alert Recipients')
    
    # Status and Tracking
    active = fields.Boolean(string='Active', default=True)
    is_exceeded = fields.Boolean(string='Threshold Exceeded', compute='_compute_is_exceeded', store=True)
    last_triggered = fields.Datetime(string='Last Triggered', help="When this threshold was last exceeded")
    trigger_count = fields.Integer(string='Trigger Count', default=0)
    
    # Cooldown and Frequency
    cooldown_hours = fields.Integer(string='Cooldown Hours', default=24, 
                                  help="Minimum hours between triggers")
    can_trigger = fields.Boolean(string='Can Trigger', compute='_compute_can_trigger', store=True)
    
    # Notes
    notes = fields.Html(string='Notes')
    
    @api.depends('threshold_type', 'condition_operator', 'threshold_value', 'asset_id')
    def _compute_is_exceeded(self):
        for threshold in self:
            exceeded = False
            
            if threshold.threshold_type == 'runtime_hours':
                current_value = threshold.asset_id.runtime_hours
                exceeded = self._evaluate_condition(current_value, threshold.condition_operator, threshold.threshold_value)
            
            elif threshold.threshold_type == 'maintenance_count':
                current_value = threshold.asset_id.maintenance_count
                exceeded = self._evaluate_condition(current_value, threshold.condition_operator, threshold.threshold_value)
            
            elif threshold.threshold_type == 'cost_threshold':
                current_value = threshold.asset_id.maintenance_cost_ytd
                exceeded = self._evaluate_condition(current_value, threshold.condition_operator, threshold.threshold_value)
            
            elif threshold.threshold_type == 'age_threshold':
                if threshold.asset_id.purchase_date:
                    age_days = (fields.Date.today() - threshold.asset_id.purchase_date).days
                    exceeded = self._evaluate_condition(age_days, threshold.condition_operator, threshold.threshold_value)
            
            elif threshold.threshold_type == 'utilization':
                current_value = threshold.asset_id.actual_utilization
                exceeded = self._evaluate_condition(current_value, threshold.condition_operator, threshold.threshold_value)
            
            threshold.is_exceeded = exceeded
    
    def _evaluate_condition(self, current_value, operator, threshold_value):
        """Evaluate if the current value meets the condition"""
        if current_value is False or current_value is None:
            return False
            
        if operator == '>':
            return current_value > threshold_value
        elif operator == '>=':
            return current_value >= threshold_value
        elif operator == '<':
            return current_value < threshold_value
        elif operator == '<=':
            return current_value <= threshold_value
        elif operator == '==':
            return current_value == threshold_value
        elif operator == '!=':
            return current_value != threshold_value
        return False
    
    @api.depends('last_triggered', 'cooldown_hours')
    def _compute_can_trigger(self):
        for threshold in self:
            if not threshold.last_triggered:
                threshold.can_trigger = True
            else:
                from datetime import timedelta
                cooldown_time = threshold.last_triggered + timedelta(hours=threshold.cooldown_hours)
                threshold.can_trigger = fields.Datetime.now() > cooldown_time
    
    def action_trigger_threshold(self):
        """Execute the threshold action when condition is met"""
        self.ensure_one()
        
        if not self.active or not self.is_exceeded or not self.can_trigger:
            return False
        
        # Update tracking
        self.write({
            'last_triggered': fields.Datetime.now(),
            'trigger_count': self.trigger_count + 1
        })
        
        # Execute action based on type
        if self.action_type == 'create_workorder':
            return self._create_work_order()
        elif self.action_type == 'send_alert':
            return self._send_alert()
        elif self.action_type == 'update_status':
            return self._update_asset_status()
        elif self.action_type == 'schedule_maintenance':
            return self._schedule_maintenance()
        elif self.action_type == 'escalate':
            return self._escalate_to_manager()
        
        return True
    
    def _create_work_order(self):
        """Create a work order based on threshold"""
        from datetime import date
        today = date.today()
        workorder_vals = {
            'name': f"Threshold Triggered - {self.name}",
            'asset_id': self.asset_id.id,
            'work_order_type': self.work_order_type,
            'priority': self.work_order_priority,
            'description': f"Automatically created due to threshold '{self.name}' being exceeded. Current value: {self._get_current_value()}",
            'state': 'draft',
            'start_date': today,
            'end_date': today  # Same day for calendar display
        }
        
        workorder = self.env['facilities.workorder'].create(workorder_vals)
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Work Order Created',
            'res_model': 'facilities.workorder',
            'view_mode': 'form',
            'res_id': workorder.id,
            'target': 'current',
        }
    
    def _send_alert(self):
        """Send alert notification"""
        message = self.alert_message or f"Threshold '{self.name}' has been exceeded on asset {self.asset_id.name}. Current value: {self._get_current_value()}"
        
        # Create activity
        self.asset_id.activity_schedule(
            'mail.mail_activity_data_todo',
            note=message,
            user_id=self.asset_id.responsible_id.id or self.env.uid
        )
        
        # Send to alert recipients
        if self.alert_recipients:
            self.env['mail.channel'].message_post(
                body=message,
                partner_ids=[user.partner_id.id for user in self.alert_recipients]
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Threshold Alert',
                'message': message,
                'type': 'warning'
            }
        }
    
    def _update_asset_status(self):
        """Update asset status based on threshold"""
        self.asset_id.write({'state': 'maintenance'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Asset Status Updated',
                'message': f'Asset {self.asset_id.name} status updated to maintenance due to threshold {self.name}',
                'type': 'info'
            }
        }
    
    def _schedule_maintenance(self):
        """Schedule maintenance based on threshold"""
        # Create maintenance schedule
        schedule_vals = {
            'name': f"Scheduled by Threshold - {self.name}",
            'asset_id': self.asset_id.id,
            'maintenance_type': self.work_order_type,
            'next_maintenance_date': fields.Date.today(),
            'notes': f"Automatically scheduled due to threshold '{self.name}' being exceeded"
        }
        
        self.env['asset.maintenance.schedule'].create(schedule_vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Maintenance Scheduled',
                'message': f'Maintenance scheduled for {self.asset_id.name} due to threshold {self.name}',
                'type': 'info'
            }
        }
    
    def _escalate_to_manager(self):
        """Escalate to manager"""
        if self.asset_id.responsible_id:
            manager = self.asset_id.responsible_id.parent_id
            if manager:
                message = f"Threshold '{self.name}' exceeded on asset {self.asset_id.name}. Escalating to manager {manager.name}."
                
                # Create activity for manager
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'res_model_id': self.env['ir.model']._get('facilities.asset').id,
                    'res_id': self.asset_id.id,
                    'user_id': manager.user_id.id,
                    'note': message
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Escalated to Manager',
                        'message': message,
                        'type': 'warning'
                    }
                }
        
        return True
    
    def _get_current_value(self):
        """Get the current value based on threshold type"""
        if self.threshold_type == 'runtime_hours':
            return f"{self.asset_id.runtime_hours} hours"
        elif self.threshold_type == 'maintenance_count':
            return f"{self.asset_id.maintenance_count} maintenance events"
        elif self.threshold_type == 'cost_threshold':
            return f"{self.asset_id.maintenance_cost_ytd} {self.asset_id.currency_id.symbol}"
        elif self.threshold_type == 'age_threshold':
            if self.asset_id.purchase_date:
                age_days = (fields.Date.today() - self.asset_id.purchase_date).days
                return f"{age_days} days"
        elif self.threshold_type == 'utilization':
            return f"{self.asset_id.actual_utilization}%"
        
        return "Unknown"
    
    @api.model
    def cron_check_thresholds(self):
        """Cron job to check all active thresholds"""
        active_thresholds = self.search([('active', '=', True)])
        for threshold in active_thresholds:
            if threshold.is_exceeded and threshold.can_trigger:
                threshold.action_trigger_threshold()