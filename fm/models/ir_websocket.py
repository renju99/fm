# -*- coding: utf-8 -*-
# ================================================================================
# WEBSOCKET CUSTOMIZATION - CURRENTLY DISABLED
# ================================================================================
# This module extends Odoo's websocket functionality to add facility-specific
# real-time channels and notifications. It has been disabled due to websocket
# connection issues.
#
# To re-enable: Uncomment the import in models/__init__.py (line 127)
# Note: Requires proper websocket configuration on port 8072
# ================================================================================

import json
import logging
from odoo import models, api
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrWebsocket(models.AbstractModel):
    _name = 'ir.websocket'
    _inherit = 'ir.websocket'

    def _build_bus_channel_list(self, channels):
        """Add facilities management specific channels to the bus"""
        try:
            channels = super()._build_bus_channel_list(channels)
            
            if request and hasattr(request, 'session') and request.session.uid:
                # Add facility-specific channels if user has access
                try:
                    facility_ids = self.env['facilities.facility'].search([]).ids
                    for facility_id in facility_ids:
                        channels.append(f'facility_{facility_id}')
                except Exception as e:
                    _logger.warning(f"Error getting facility IDs for WebSocket channels: {e}")
            
            return channels
        except Exception as e:
            _logger.error(f"Error building bus channel list: {e}")
            return channels or []

    @api.model
    def _get_im_status(self, *args, **kwargs):
        """Override to handle status updates"""
        try:
            return super()._get_im_status(*args, **kwargs)
        except Exception as e:
            _logger.warning(f"Error in _get_im_status: {e}")
            return {}

    @api.model
    def send_maintenance_alert(self, workorder_id, alert_type='reminder'):
        """Send real-time maintenance alerts"""
        try:
            workorder = self.env['facilities.workorder'].browse(workorder_id)
            if workorder.exists():
                channel = f'maintenance_team_{workorder.maintenance_team_id.id}'
                message = {
                    'type': 'maintenance_alert',
                    'workorder_id': workorder_id,
                    'workorder_name': workorder.name,
                    'asset_name': workorder.asset_id.name,
                    'alert_type': alert_type,
                    'priority': workorder.priority,
                    'scheduled_date': workorder.scheduled_date,
                }
                self.env['bus.bus']._sendone(channel, 'maintenance_alert', message)
        except Exception as e:
            _logger.error(f"Error sending maintenance alert: {e}")


class BusBus(models.Model):
    _inherit = 'bus.bus'

    def _sendone(self, channel, message_type, message):
        """Override to improve connection reliability"""
        try:
            return super()._sendone(channel, message_type, message)
        except Exception as e:
            _logger.warning(f"Failed to send bus message: {e}")
            # Attempt to reconnect and retry once
            try:
                self.env.cr.commit()
                return super()._sendone(channel, message_type, message)
            except Exception as retry_error:
                _logger.error(f"Failed to send bus message after retry: {retry_error}")
                return False

    def _sendmany(self, notifications):
        """Override to improve connection reliability for multiple notifications"""
        try:
            return super()._sendmany(notifications)
        except Exception as e:
            _logger.warning(f"Failed to send bus messages to multiple channels: {e}")
            # Attempt to reconnect and retry once
            try:
                self.env.cr.commit()
                return super()._sendmany(notifications)
            except Exception as retry_error:
                _logger.error(f"Failed to send bus messages after retry: {retry_error}")
                return False

    @api.model
    def _poll(self, channels, last, options=None):
        """Override to add better error handling for polling"""
        try:
            return super()._poll(channels, last, options)
        except Exception as e:
            _logger.warning(f"Error in bus polling: {e}")
            # Return empty result instead of failing
            return {
                'channels': channels,
                'notifications': [],
                'last': last,
            }