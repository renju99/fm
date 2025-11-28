# -*- coding: utf-8 -*-

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class AssetPerformanceStandardReport(models.AbstractModel):
    _name = 'report.facilities_management.asset_performance_standard'
    _description = 'Standard Asset Performance Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for the standard asset performance report."""
        docs = self.env['facilities.asset.performance.dashboard'].browse(docids)
        
        # Ensure all dashboards are processed
        for doc in docs:
            if doc.state != 'completed':
                doc.action_process()
        
        return {
            'doc_ids': docids,
            'doc_model': 'facilities.asset.performance.dashboard',
            'docs': docs,
            'data': data,
        }
