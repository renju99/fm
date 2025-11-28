from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import re
import qrcode
import base64
from io import BytesIO
import json


class FacilitiesSpaceBooking(models.Model):
    _name = 'facilities.space.booking'
    _description = 'Space/Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'

    name = fields.Char('Booking Reference', required=True, readonly=True, default=lambda self: _('New'))
    room_id = fields.Many2one('facilities.room', string='Room', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Booked By', default=lambda self: self.env.user, tracking=True)
    start_datetime = fields.Datetime('Start Time', required=True, tracking=True)
    end_datetime = fields.Datetime('End Time', required=True, tracking=True)
    purpose = fields.Char('Purpose', tracking=True)
    attendees = fields.Integer('Number of Attendees')
    notes = fields.Html('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')

    # Enhanced fields
    booking_type = fields.Selection([
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('training', 'Training'),
        ('workshop', 'Workshop'),
        ('conference', 'Conference'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ], string='Booking Type', default='meeting', tracking=True, required=True)

    contact_email = fields.Char('Contact Email', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)

    # Recurrence fields
    is_recurring = fields.Boolean('Recurring Booking', tracking=True)
    recurrence_rule = fields.Char('Recurrence Rule',
                                  help="iCal-style recurrence rule (e.g., FREQ=WEEKLY;BYDAY=MO,WE,FR)")
    parent_booking_id = fields.Many2one('facilities.space.booking', string='Parent Booking')
    child_booking_ids = fields.One2many('facilities.space.booking', 'parent_booking_id', string='Child Bookings')

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', default=lambda self: [(6, 0, [])])

    # External guests
    is_external_guest = fields.Boolean('Has External Guests', tracking=True)
    external_guest_names = fields.Html('External Guest Names', help="List external guest names, one per line")

    # NEW ENHANCED FEATURES
    
    # QR Code Generation
    qr_code = fields.Binary('QR Code', compute='_compute_qr_code', store=True)
    qr_code_filename = fields.Char('QR Code Filename', default='booking_qr.png')
    
    # Booking Templates
    template_id = fields.Many2one('facilities.booking.template', string='Booking Template')
    is_template = fields.Boolean('Save as Template')
    template_name = fields.Char('Template Name')
    
    # Capacity Management
    required_capacity = fields.Integer('Required Capacity', default=1)
    room_capacity = fields.Integer('Room Capacity', related='room_id.capacity', store=True)
    capacity_utilization = fields.Float('Capacity Utilization %', compute='_compute_capacity_utilization', store=True)
    
    # Cost Calculation
    hourly_rate = fields.Float('Hourly Rate', related='room_id.hourly_rate', store=True)
    total_cost = fields.Float('Total Cost', compute='_compute_total_cost', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Room Equipment
    required_equipment_ids = fields.Many2many('facilities.room.equipment', string='Required Equipment', default=lambda self: [(6, 0, [])])
    equipment_availability = fields.Html('Equipment Availability', compute='_compute_equipment_availability', default='')
    
    # Check-in/Check-out
    check_in_time = fields.Datetime('Check-in Time')
    check_out_time = fields.Datetime('Check-out Time')
    auto_check_in = fields.Boolean('Auto Check-in', default=False)
    auto_check_out = fields.Boolean('Auto Check-out', default=False)
    
    # Approval Workflow
    approval_required = fields.Boolean('Approval Required', compute='_compute_approval_required', store=True)
    approved_by = fields.Many2one('res.users', string='Approved By')
    approval_date = fields.Datetime('Approval Date')
    rejection_reason = fields.Html('Rejection Reason')
    
    # Integration Fields
    calendar_event_id = fields.Char('Calendar Event ID')
    external_booking_ref = fields.Char('External Booking Reference')
    portal_access_token = fields.Char('Portal Access Token', default=lambda self: self._generate_access_token())
    
    # Notification Settings
    notification_settings = fields.Html('Notification Settings', default='{"email": true, "sms": false, "app": true}')
    reminder_sent = fields.Boolean('Reminder Sent', default=False)
    
    # Priority and Rating
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='normal', string='Priority', tracking=True)
    
    rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐')
    ], string='Rating')
    feedback = fields.Html('Feedback')

    # Computed fields
    duration_hours = fields.Float('Duration (Hours)', compute='_compute_duration_hours', store=True)
    is_holiday_conflict = fields.Boolean('Holiday Conflict', compute='_compute_holiday_conflict')
    recurring_display = fields.Char('Recurrence', compute='_compute_recurring_display')
    booking_status_display = fields.Char('Status Display', compute='_compute_status_display')
    is_overdue = fields.Boolean('Is Overdue', compute='_compute_is_overdue', store=True)
    
    def _generate_access_token(self):
        import secrets
        return secrets.token_urlsafe(32)

    @api.depends('name', 'room_id', 'start_datetime')
    def _compute_qr_code(self):
        for booking in self:
            if booking.name and booking.room_id:
                qr_data = {
                    'booking_id': booking.id,
                    'booking_ref': booking.name,
                    'room': booking.room_id.name,
                    'start_time': booking.start_datetime.isoformat() if booking.start_datetime else '',
                    'access_token': booking.portal_access_token
                }
                
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(json.dumps(qr_data))
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                booking.qr_code = base64.b64encode(buffer.getvalue())
            else:
                booking.qr_code = False

    @api.depends('required_capacity', 'room_capacity')
    def _compute_capacity_utilization(self):
        for booking in self:
            if booking.room_capacity and booking.required_capacity:
                booking.capacity_utilization = (booking.required_capacity / booking.room_capacity) * 100
            else:
                booking.capacity_utilization = 0.0

    @api.depends('duration_hours', 'hourly_rate')
    def _compute_total_cost(self):
        for booking in self:
            booking.total_cost = booking.duration_hours * booking.hourly_rate

    @api.depends('required_equipment_ids')
    def _compute_equipment_availability(self):
        for booking in self:
            if not booking.required_equipment_ids:
                booking.equipment_availability = ''
                continue
            if booking.required_equipment_ids and booking.start_datetime and booking.end_datetime:
                availability_info = []
                for equipment in booking.required_equipment_ids:
                    # Check if equipment is available during booking time
                    conflicting_bookings = self.search([
                        ('id', '!=', booking.id),
                        ('required_equipment_ids', 'in', equipment.id),
                        ('state', 'in', ['confirmed', 'in_progress']),
                        ('start_datetime', '<', booking.end_datetime),
                        ('end_datetime', '>', booking.start_datetime),
                    ])
                    
                    if conflicting_bookings:
                        availability_info.append(f"{equipment.name}: Not Available (conflicting bookings)")
                    else:
                        availability_info.append(f"{equipment.name}: Available")
                
                booking.equipment_availability = '\n'.join(availability_info)
            else:
                booking.equipment_availability = ''

    @api.depends('booking_type', 'total_cost', 'duration_hours')
    def _compute_approval_required(self):
        for booking in self:
            # Approval required for events, high-cost bookings, or long duration
            booking.approval_required = (
                booking.booking_type == 'event' or 
                booking.total_cost > 1000 or 
                booking.duration_hours > 8
            )

    @api.depends('state', 'check_in_time', 'check_out_time')
    def _compute_status_display(self):
        for booking in self:
            if booking.state == 'confirmed' and booking.check_in_time:
                booking.booking_status_display = 'Checked In'
            elif booking.state == 'completed' and booking.check_out_time:
                booking.booking_status_display = 'Checked Out'
            else:
                booking.booking_status_display = dict(booking._fields['state'].selection).get(booking.state, booking.state)

    @api.depends('end_datetime', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for booking in self:
            booking.is_overdue = (
                booking.state in ['confirmed', 'in_progress'] and 
                booking.end_datetime and 
                booking.end_datetime < now
            )

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration_hours(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                delta = booking.end_datetime - booking.start_datetime
                booking.duration_hours = delta.total_seconds() / 3600.0
            else:
                booking.duration_hours = 0.0

    @api.depends('start_datetime', 'end_datetime')
    def _compute_holiday_conflict(self):
        for booking in self:
            booking.is_holiday_conflict = False

    @api.depends('is_recurring', 'recurrence_rule')
    def _compute_recurring_display(self):
        for booking in self:
            if booking.is_recurring and booking.recurrence_rule:
                rule = booking.recurrence_rule
                if 'FREQ=DAILY' in rule:
                    booking.recurring_display = 'Daily'
                elif 'FREQ=WEEKLY' in rule:
                    booking.recurring_display = 'Weekly'
                elif 'FREQ=MONTHLY' in rule:
                    booking.recurring_display = 'Monthly'
                else:
                    booking.recurring_display = 'Custom'
            else:
                booking.recurring_display = ''

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_validity(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                if booking.end_datetime <= booking.start_datetime:
                    raise ValidationError(_("End time must be after start time."))

                if booking.is_holiday_conflict:
                    raise ValidationError(_("Booking conflicts with company holidays."))

    @api.constrains('room_id', 'start_datetime', 'end_datetime')
    def _check_booking_conflicts(self):
        for booking in self:
            if not booking.room_id or not booking.start_datetime or not booking.end_datetime:
                continue
            domain = [
                ('room_id', '=', booking.room_id.id),
                ('state', 'in', ['pending', 'confirmed']),
                ('id', '!=', booking.id),
                ('start_datetime', '<', booking.end_datetime),
                ('end_datetime', '>', booking.start_datetime),
            ]
            if self.search_count(domain):
                raise ValidationError(_("This room is already booked for the selected time."))

    @api.constrains('booking_type', 'department_id')
    def _check_event_department(self):
        for booking in self:
            if booking.booking_type == 'event' and not booking.department_id:
                raise ValidationError(_("Department must be specified for Event bookings."))

    @api.constrains('is_recurring', 'recurrence_rule')
    def _check_recurrence_rule(self):
        for booking in self:
            if booking.is_recurring and booking.recurrence_rule:
                if not self._validate_recurrence_rule(booking.recurrence_rule):
                    raise ValidationError(
                        _("Invalid recurrence rule format. Please use iCal format (e.g., FREQ=WEEKLY;BYDAY=MO,WE,FR)."))

    def _validate_recurrence_rule(self, rule):
        if not rule:
            return False

        if 'FREQ=' not in rule.upper():
            return False

        valid_freq = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
        freq_match = re.search(r'FREQ=([A-Z]+)', rule.upper())
        if freq_match and freq_match.group(1) not in valid_freq:
            return False

        return True

    @api.constrains('contact_email')
    def _check_contact_email(self):
        for booking in self:
            if booking.contact_email:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, booking.contact_email):
                    raise ValidationError(_("Please enter a valid email address."))

    @api.constrains('required_capacity', 'room_capacity')
    def _check_capacity(self):
        for booking in self:
            if booking.required_capacity and booking.room_capacity:
                if booking.required_capacity > booking.room_capacity:
                    raise ValidationError(_("Required capacity (%d) exceeds room capacity (%d).") % 
                                        (booking.required_capacity, booking.room_capacity))

    @api.constrains('required_equipment_ids')
    def _check_equipment_availability(self):
        for booking in self:
            if booking.required_equipment_ids and booking.start_datetime and booking.end_datetime:
                for equipment in booking.required_equipment_ids:
                    conflicting_bookings = self.search([
                        ('id', '!=', booking.id),
                        ('required_equipment_ids', 'in', equipment.id),
                        ('state', 'in', ['confirmed', 'in_progress']),
                        ('start_datetime', '<', booking.end_datetime),
                        ('end_datetime', '>', booking.start_datetime),
                    ])
                    
                    if conflicting_bookings:
                        raise ValidationError(_("Equipment '%s' is not available during the selected time.") % equipment.name)

    def create_room_manager_activity(self):
        for booking in self:  # Use 'self' as a recordset in case of multi-create
            manager_employee = booking.room_id.manager_id
            if booking.booking_type == 'event' and booking.state == 'pending' and manager_employee:
                manager_user = manager_employee.user_id
                if manager_user:  # Ensure the employee has a linked Odoo user
                    booking.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=manager_user.id,  # <--- CORRECTED: Use the res.users ID
                        summary='Event booking approval required',
                        note=f'Please review and approve booking {booking.name} for room {booking.room_id.name}.',
                    )
                else:
                    # Optional: Log a warning if manager has no user, or raise error if critical
                    self.env.cr.execute(
                        f"INSERT INTO ir_logging (create_date, create_uid, name, level, message, type, dbname, func, line) VALUES (NOW(), {self.env.uid}, 'facilities.space.booking', 'WARNING', 'Room manager {manager_employee.name} for room {booking.room_id.name} does not have an associated Odoo user. Cannot create approval activity.', 'server', '{self.env.cr.dbname}', 'create_room_manager_activity', '{__name__}.py:L{self._get_linenumber()}');")
                    _logger.warning(
                        "Room manager %s for room %s does not have an associated Odoo user. Cannot create approval activity.",
                        manager_employee.name, booking.room_id.name)

    def schedule_reminder_emails(self):
        for booking in self:
            if booking.state == 'confirmed' and booking.start_datetime:
                reminder_date = booking.start_datetime - timedelta(hours=24)
                if reminder_date > datetime.now():
                    booking.activity_schedule(
                        'mail.mail_activity_data_email',
                        date_deadline=reminder_date.date(),
                        user_id=booking.user_id.id,
                        summary='Booking Reminder',
                        note=f'Reminder: You have a booking tomorrow - {booking.name}',
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.space.booking') or _('New')

            if vals.get('booking_type') == 'event':
                vals['state'] = 'pending'
            else:
                vals['state'] = 'confirmed'

        records = super().create(vals_list)

        for rec in records:
            # Check if an hr_employee and linked res_users is available for activity creation
            manager_employee = rec.room_id.manager_id
            if rec.booking_type == 'event' and rec.state == 'pending' and manager_employee and manager_employee.user_id:
                rec.create_room_manager_activity()  # This method will now handle fetching user_id correctly

            if rec.state == 'confirmed':
                rec.schedule_reminder_emails()
                template = self.env.ref('facilities_management.mail_template_space_booking_confirmed',
                                        raise_if_not_found=False)
                if template:
                    template.send_mail(rec.id, force_send=True)

        return records

    def write(self, vals):
        old_state = {rec.id: rec.state for rec in self}
        result = super().write(vals)

        for rec in self:
            if vals.get('state') == 'confirmed' and old_state.get(rec.id) != 'confirmed':
                template = self.env.ref('facilities_management.mail_template_space_booking_confirmed',
                                        raise_if_not_found=False)
                if template:
                    template.send_mail(rec.id, force_send=True)
                rec.schedule_reminder_emails()

        return result

    def action_confirm(self):
        for booking in self:
            if booking.booking_type == 'event' and booking.state == 'pending':
                manager_employee = booking.room_id.manager_id

                if not manager_employee:
                    raise ValidationError(_("No room manager assigned to this room. Event booking cannot be approved."))

                manager_user = manager_employee.user_id

                if not manager_user:
                    raise ValidationError(_("The assigned room manager (%s) does not have an associated Odoo user.") % (
                        manager_employee.name))

                if self.env.user.id != manager_user.id:
                    raise ValidationError(_("Only the room manager (%s) can approve this event booking.") % (
                        manager_employee.name))

                # Mark activity as done for the correct user
                activities = self.env['mail.activity'].search([
                    ('res_model', '=', 'facilities.space.booking'),
                    ('res_id', '=', booking.id),
                    ('user_id', '=', manager_user.id),  # <--- CORRECTED: Use the res.users ID here
                    ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                    ('summary', '=', 'Event booking approval required'),
                ])
                activities.action_feedback(feedback='Approved')
                booking.write({'state': 'confirmed'})
            elif booking.state == 'draft':
                booking.write({'state': 'confirmed'})
            elif booking.state == 'pending' and booking.booking_type != 'event':
                booking.write({'state': 'confirmed'})
            else:
                raise ValidationError(_("Booking cannot be confirmed from its current state."))

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_create_recurring_bookings(self):
        for booking in self:
            if not booking.is_recurring or not booking.recurrence_rule:
                continue

            if 'FREQ=WEEKLY' in booking.recurrence_rule.upper():
                current_date = booking.start_datetime
                duration = booking.end_datetime - booking.start_datetime

                for i in range(1, 11):
                    next_start = current_date + timedelta(weeks=i)
                    next_end = next_start + duration

                    existing = self.search([
                        ('room_id', '=', booking.room_id.id),
                        ('start_datetime', '=', next_start),
                        ('end_datetime', '=', next_end),
                    ])

                    if not existing:
                        new_booking_state = 'pending' if booking.booking_type == 'event' else 'confirmed'
                        self.create({
                            'room_id': booking.room_id.id,
                            'user_id': booking.user_id.id,
                            'start_datetime': next_start,
                            'end_datetime': next_end,
                            'purpose': booking.purpose,
                            'attendees': booking.attendees,
                            'notes': booking.notes,
                            'booking_type': booking.booking_type,
                            'contact_email': booking.contact_email,
                            'department_id': booking.department_id.id if booking.department_id else False,
                            'is_external_guest': booking.is_external_guest,
                            'external_guest_names': booking.external_guest_names,
                            'is_recurring': False,
                            'state': new_booking_state,
                        })

    def action_check_in(self):
        """Manual or automatic check-in"""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_("Only confirmed bookings can be checked in."))
        
        self.write({
            'check_in_time': fields.Datetime.now(),
            'state': 'in_progress'
        })
        
        self.message_post(body=_("Booking checked in at %s") % fields.Datetime.now())

    def action_check_out(self):
        """Manual or automatic check-out"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_("Only in-progress bookings can be checked out."))
        
        self.write({
            'check_out_time': fields.Datetime.now(),
            'state': 'completed'
        })
        
        self.message_post(body=_("Booking checked out at %s") % fields.Datetime.now())

    def action_approve(self):
        """Approve booking"""
        self.ensure_one()
        if not self.approval_required:
            raise UserError(_("This booking does not require approval."))
        
        self.write({
            'state': 'confirmed',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        self.message_post(body=_("Booking approved by %s") % self.env.user.name)

    def action_reject(self):
        """Reject booking with reason"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Booking',
            'res_model': 'facilities.booking.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id}
        }

    def action_create_template(self):
        """Create booking template from current booking"""
        self.ensure_one()
        if not self.template_name:
            raise UserError(_("Please provide a template name."))
        
        template_data = {
            'name': self.template_name,
            'booking_type': self.booking_type,
            'purpose': self.purpose,
            'attendees': self.attendees,
            'notes': self.notes,
            'department_id': self.department_id.id,
            'required_equipment_ids': [(6, 0, self.required_equipment_ids.ids)],
            'is_external_guest': self.is_external_guest,
            'priority': self.priority,
            'notification_settings': self.notification_settings,
        }
        
        template = self.env['facilities.booking.template'].create(template_data)
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking Template',
            'res_model': 'facilities.booking.template',
            'res_id': template.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_send_reminder(self):
        """Send booking reminder"""
        self.ensure_one()
        template = self.env.ref('facilities_management.mail_template_space_booking_reminder', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
            self.reminder_sent = True

    def action_view_rating(self):
        """View booking rating details"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking Rating',
            'res_model': 'facilities.space.booking',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'flags': {'mode': 'readonly'},
        }

    def action_view_portal(self):
        """Get portal view URL"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my/booking/{self.id}?access_token={self.portal_access_token}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': portal_url,
            'target': 'new',
        }

    @api.model
    def auto_check_in_out(self):
        """Cron job for automatic check-in/out"""
        now = fields.Datetime.now()
        
        # Auto check-in
        bookings_to_check_in = self.search([
            ('state', '=', 'confirmed'),
            ('auto_check_in', '=', True),
            ('start_datetime', '<=', now),
            ('check_in_time', '=', False),
        ])
        
        for booking in bookings_to_check_in:
            booking.action_check_in()
        
        # Auto check-out
        bookings_to_check_out = self.search([
            ('state', '=', 'in_progress'),
            ('auto_check_out', '=', True),
            ('end_datetime', '<=', now),
            ('check_out_time', '=', False),
        ])
        
        for booking in bookings_to_check_out:
            booking.action_check_out()

    @api.model
    def send_reminder_notifications(self):
        """Cron job to send reminder notifications"""
        reminder_time = fields.Datetime.now() + timedelta(hours=24)
        
        bookings = self.search([
            ('state', '=', 'confirmed'),
            ('start_datetime', '<=', reminder_time),
            ('start_datetime', '>', fields.Datetime.now()),
            ('reminder_sent', '=', False),
        ])
        
        for booking in bookings:
            booking.action_send_reminder()

    @api.model
    def send_overdue_notifications(self):
        """Send notifications for overdue bookings"""
        # Find overdue bookings and notify
        overdue_bookings = self.search([
            ('is_overdue', '=', True),
            ('state', 'in', ['confirmed', 'in_progress'])
        ])
        
        for booking in overdue_bookings:
            booking.message_post(
                body=f'Booking {booking.name} is overdue. Please check out or extend the booking.',
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

    def action_view_my_bookings(self):
        """View my bookings"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Bookings',
            'res_model': 'facilities.space.booking',
            'view_mode': 'kanban,list,form,calendar',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {
                'search_default_my_bookings': 1,
                'default_user_id': self.env.user.id,
            },
            'target': 'current',
        }

    def action_view_today_bookings(self):
        """View today's bookings"""
        today = fields.Date.today()
        tomorrow = today + timedelta(days=1)
        
        return {
            'type': 'ir.actions.act_window',
            'name': "Today's Bookings",
            'res_model': 'facilities.space.booking',
            'view_mode': 'kanban,list,form,calendar',
            'domain': [
                ('start_datetime', '>=', today),
                ('start_datetime', '<', tomorrow)
            ],
            'context': {
                'search_default_today': 1,
                'default_start_datetime': fields.Datetime.now(),
            },
            'target': 'current',
        }

    def action_view_utilization_report(self):
        """View utilization report"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Utilization Report',
            'res_model': 'facilities.space.booking',
            'view_mode': 'pivot,graph',
            'domain': [('state', 'in', ['confirmed', 'completed'])],
            'context': {
                'group_by': ['room_id'],
                'search_default_confirmed': 1,
            },
            'target': 'current',
        }

    def action_view_cost_analysis(self):
        """View cost analysis"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cost Analysis',
            'res_model': 'facilities.space.booking',
            'view_mode': 'pivot,graph',
            'domain': [('state', 'in', ['confirmed', 'completed']), ('total_cost', '>', 0)],
            'context': {
                'group_by': ['department_id'],
                'search_default_confirmed': 1,
            },
            'target': 'current',
        }

    def action_view_trends(self):
        """View booking trends"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking Trends',
            'res_model': 'facilities.space.booking',
            'view_mode': 'graph,pivot',
            'domain': [('state', 'in', ['confirmed', 'completed'])],
            'context': {
                'group_by': ['start_datetime:month'],
                'search_default_confirmed': 1,
            },
            'target': 'current',
        }

    def action_view_department_analysis(self):
        """View department analysis"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Department Analysis',
            'res_model': 'facilities.space.booking',
            'view_mode': 'graph,pivot',
            'domain': [('state', 'in', ['confirmed', 'completed']), ('department_id', '!=', False)],
            'context': {
                'group_by': ['department_id'],
                'search_default_confirmed': 1,
            },
            'target': 'current',
        }

    def action_view_booking_patterns(self):
        """View booking patterns"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking Patterns',
            'res_model': 'facilities.space.booking',
            'view_mode': 'graph,pivot',
            'domain': [('state', 'in', ['confirmed', 'completed'])],
            'context': {
                'group_by': ['booking_type', 'start_datetime:week'],
                'search_default_confirmed': 1,
            },
            'target': 'current',
        }

    # ==============================
    # Dashboard Data for Space Booking
    # ==============================
    @api.model
    def get_space_booking_dashboard_data(self, period='current_month', booking_type='all', date_from=None, date_to=None):
        try:
            # Determine date range
            today = fields.Date.context_today(self)
            if period == 'current_month':
                start = fields.Date.to_date(str(today).replace(str(today)[8:], '01'))
                end = today
            elif period == 'last_30_days':
                end = today
                start = end - timedelta(days=30)
            elif period == 'current_year':
                start = fields.Date.to_date(f"{str(today)[:4]}-01-01")
                end = today
            elif period == 'custom_range' and date_from and date_to:
                start = fields.Date.to_date(date_from)
                end = fields.Date.to_date(date_to)
            else:
                # default fallback
                end = today
                start = end - timedelta(days=30)

            domain = [('start_datetime', '>=', fields.Datetime.to_datetime(f"{start} 00:00:00")),
                      ('start_datetime', '<=', fields.Datetime.to_datetime(f"{end} 23:59:59"))]
            if booking_type != 'all':
                domain.append(('booking_type', '=', booking_type))

            bookings = self.search(domain)
            confirmed = bookings.filtered(lambda b: b.state in ['confirmed', 'in_progress', 'completed'])
            pending = bookings.filtered(lambda b: b.state == 'pending')

            # Upcoming in next 7 days
            now_dt = fields.Datetime.now()
            week_later = now_dt + timedelta(days=7)
            upcoming = self.search([
                ('start_datetime', '>=', now_dt),
                ('start_datetime', '<', week_later),
                ('state', 'in', ['confirmed', 'in_progress'])
            ])

            # Aggregations
            total_cost = sum(confirmed.mapped('total_cost')) if confirmed else 0.0
            avg_capacity = 0.0
            if confirmed:
                vals = [b.capacity_utilization for b in confirmed if b.capacity_utilization is not None]
                avg_capacity = sum(vals) / len(vals) if vals else 0.0

            # Distribution by type and room
            by_type = {}
            by_room = {}
            for b in bookings:
                t = b.booking_type or 'other'
                by_type[t] = by_type.get(t, 0) + 1
                r = b.room_id.name or 'Unassigned'
                by_room[r] = by_room.get(r, 0) + 1

            # Simple trend (bookings per day)
            trends_map = {}
            for b in bookings:
                day_key = fields.Date.to_string(fields.Date.to_date(b.start_datetime.date()))
                trends_map[day_key] = trends_map.get(day_key, 0) + 1
            trends = [{"date": k, "count": v} for k, v in sorted(trends_map.items())]

            return {
                'period': period,
                'summary': {
                    'total_bookings': len(bookings),
                    'confirmed_bookings': len(confirmed),
                    'pending_approvals': len(pending),
                    'upcoming_week': len(upcoming),
                    'avg_capacity_utilization': avg_capacity,
                    'total_cost': total_cost,
                },
                'trends': {
                    'bookings_per_day': trends,
                },
                'distribution': {
                    'by_type': by_type,
                    'by_room': by_room,
                },
                'upcoming_bookings': [
                    {
                        'id': b.id,
                        'start': fields.Datetime.to_string(b.start_datetime) if b.start_datetime else '',
                        'end': fields.Datetime.to_string(b.end_datetime) if b.end_datetime else '',
                        'room': b.room_id.name if b.room_id else '',
                        'type': b.booking_type or '',
                        'requester': b.user_id.name if b.user_id else '',
                    }
                    for b in upcoming.sorted(key=lambda r: r.start_datetime)[:10]
                ],
            }
        except Exception as e:
            return {'error': str(e)}
    
    @api.constrains('required_capacity', 'room_id')
    def _check_capacity_requirements(self):
        """Validate booking capacity doesn't exceed room capacity."""
        for booking in self:
            if booking.required_capacity and booking.room_id and booking.room_id.capacity:
                if booking.required_capacity > booking.room_id.capacity:
                    raise ValidationError(_("Required capacity (%d) exceeds room capacity (%d).") % 
                                        (booking.required_capacity, booking.room_id.capacity))
    
    @api.constrains('start_datetime', 'end_datetime')
    def _check_booking_duration(self):
        """Validate booking duration is reasonable."""
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                duration = booking.end_datetime - booking.start_datetime
                
                # Minimum duration: 15 minutes
                if duration.total_seconds() < 900:  # 15 minutes
                    raise ValidationError(_("Booking duration must be at least 15 minutes."))
                
                # Maximum duration: 30 days
                if duration.days > 30:
                    raise ValidationError(_("Booking duration cannot exceed 30 days."))
    
    @api.constrains('start_datetime')
    def _check_advance_booking_limit(self):
        """Validate booking is not too far in advance."""
        from datetime import datetime, timedelta
        for booking in self:
            if booking.start_datetime:
                max_advance = datetime.now() + timedelta(days=365)  # 1 year advance
                if booking.start_datetime > max_advance:
                    raise ValidationError(_("Bookings cannot be made more than 1 year in advance."))
    
    @api.constrains('booking_type', 'department_id')
    def _check_department_booking_rules(self):
        """Validate department-specific booking rules."""
        for booking in self:
            if booking.booking_type == 'internal' and not booking.department_id:
                raise ValidationError(_("Department is required for internal bookings."))
    
    @api.constrains('state', 'start_datetime')
    def _check_past_booking_changes(self):
        """Prevent changes to past bookings."""
        from datetime import datetime
        for booking in self:
            if booking._origin.id and booking.start_datetime and booking.start_datetime < datetime.now():
                if booking._origin.state != booking.state:
                    raise ValidationError(_("Cannot change status of past bookings."))
    
    @api.constrains('is_recurring', 'recurrence_rule')
    def _check_recurring_rules(self):
        """Validate recurring booking rules."""
        for booking in self:
            if booking.is_recurring and not booking.recurrence_rule:
                raise ValidationError(_("Recurrence rule is required for recurring bookings."))
            
            if booking.is_recurring and booking.booking_type == 'external':
                raise ValidationError(_("External bookings cannot be recurring."))