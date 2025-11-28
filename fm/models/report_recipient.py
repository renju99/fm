from odoo import api, fields, models, _


class FacilitiesReportRecipient(models.Model):
    _name = 'facilities.report.recipient'
    _description = 'Report Recipients per Report and Facility'
    _rec_name = 'name'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    active = fields.Boolean(default=True)

    report_action_id = fields.Many2one(
        'ir.actions.report',
        string='Report',
        required=True,
        help="Select the report action to configure recipients for.",
    )
    report_name = fields.Char(string='Technical Report Name', related='report_action_id.report_name', store=True)
    report_model = fields.Char(string='Report Model', related='report_action_id.model', store=True)

    facility_id = fields.Many2one('facilities.facility', string='Facility')

    user_ids = fields.Many2many(
        'res.users',
        'facilities_report_recipient_user_rel',
        'recipient_id',
        'user_id',
        string='Recipients (Users)',
        help='Users who should receive this report via email.',
    )

    description = fields.Text()

    _sql_constraints = [
        (
            'unique_report_facility',
            'unique(report_action_id, facility_id)',
            'There is already a recipient configuration for this report and facility.',
        ),
    ]

    @api.depends('report_action_id', 'facility_id')
    def _compute_name(self):
        for rec in self:
            base = rec.report_action_id.name or rec.report_name or _('Report')
            if rec.facility_id:
                rec.name = f"{base} - {rec.facility_id.display_name}"
            else:
                rec.name = base

    @api.model
    def get_recipient_emails(self, report_action_xmlid=None, report_action=None, facility=None):
        """Resolve recipient email list for a given report and optional facility.

        Returns a list of unique email strings.
        """
        if report_action is None and report_action_xmlid:
            try:
                report_action = self.env.ref(report_action_xmlid)
            except ValueError:
                report_action = None

        if not report_action:
            return []

        domain = [('report_action_id', '=', report_action.id), ('active', '=', True)]
        if facility:
            domain = ['|', ('facility_id', '=', False), ('facility_id', '=', facility.id)]
        records = self.search(domain, order='facility_id desc')

        emails = []
        seen = set()
        for rec in records:
            for user in rec.user_ids:
                email = user.email or (user.partner_id and user.partner_id.email)
                if email and email not in seen:
                    seen.add(email)
                    emails.append(email)
        return emails

from odoo import api, fields, models, _


class FacilitiesReportRecipient(models.Model):
    _name = 'facilities.report.recipient'
    _description = 'Report Recipients per Report and Facility'
    _rec_name = 'name'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    active = fields.Boolean(default=True)

    report_action_id = fields.Many2one(
        'ir.actions.report',
        string='Report',
        required=True,
        help="Select the report action to configure recipients for.",
    )
    report_name = fields.Char(string='Technical Report Name', related='report_action_id.report_name', store=True)
    report_model = fields.Char(string='Report Model', related='report_action_id.model', store=True)

    facility_id = fields.Many2one('facilities.facility', string='Facility')

    user_ids = fields.Many2many(
        'res.users',
        'facilities_report_recipient_user_rel',
        'recipient_id',
        'user_id',
        string='Recipients (Users)',
        help='Users who should receive this report via email.',
    )

    description = fields.Text()

    _sql_constraints = [
        (
            'unique_report_facility',
            'unique(report_action_id, facility_id)',
            'There is already a recipient configuration for this report and facility.',
        ),
    ]

    @api.depends('report_action_id', 'facility_id')
    def _compute_name(self):
        for rec in self:
            base = rec.report_action_id.name or rec.report_name or _('Report')
            if rec.facility_id:
                rec.name = f"{base} - {rec.facility_id.display_name}"
            else:
                rec.name = base

    @api.model
    def get_recipient_emails(self, report_action_xmlid=None, report_action=None, facility=None):
        """Resolve recipient email list for a given report and optional facility.

        Returns a list of unique email strings.
        """
        Report = self.env['ir.actions.report']
        if report_action is None and report_action_xmlid:
            try:
                report_action = self.env.ref(report_action_xmlid)
            except ValueError:
                report_action = None

        if not report_action:
            return []

        domain = [('report_action_id', '=', report_action.id), ('active', '=', True)]
        if facility:
            domain = ['|', ('facility_id', '=', False), ('facility_id', '=', facility.id)]
        records = self.search(domain, order='facility_id desc')

        emails = []
        seen = set()
        for rec in records:
            for user in rec.user_ids:
                email = user.email or (user.partner_id and user.partner_id.email)
                if email and email not in seen:
                    seen.add(email)
                    emails.append(email)
        return emails

