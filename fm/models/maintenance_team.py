from odoo import fields, models, api

class MaintenanceTeam(models.Model):
    _name = 'maintenance.team'
    _description = 'Maintenance Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    SERVICE_TYPE_SELECTION = [
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Cleaning'),
        ('security', 'Security'),
        ('esg', 'ESG Compliance'),
        ('hse', 'HSE Incident')
    ]

    name = fields.Char(string="Team Name", required=True)
    service_type = fields.Selection(
        SERVICE_TYPE_SELECTION,
        string="Service Type",
        required=True,
        default='maintenance',
        tracking=True,
        help="Department/Service this team belongs to."
    )
    leader_id = fields.Many2one(
        'hr.employee', string="Team Leader",
        domain="[('work_email', '!=', False)]",
        help="The employee responsible for this maintenance team."
    )
    member_ids = fields.Many2many(
        'hr.employee', 'maintenance_team_employee_rel',
        'team_id', 'employee_id', string="Team Members",
        domain="[('work_email', '!=', False)]",
        help="Employees who are part of this maintenance team."
    )
    request_ids = fields.One2many(
        'facilities.workorder', 'maintenance_team_id', string="Maintenance Work Orders"
    )
    workorder_count = fields.Integer(
        string="Number of Work Orders", compute='_compute_workorder_count'
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company
    )
    color = fields.Integer(string='Color', default=0, help="Color index for calendar and kanban views")

    @api.depends('request_ids')
    def _compute_workorder_count(self):
        for team in self:
            team.workorder_count = len(team.request_ids)