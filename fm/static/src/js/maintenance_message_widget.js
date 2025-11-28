/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Thread } from "@mail/core/common/thread";

/**
 * Patch the mail thread widget to properly render HTML content in maintenance work orders
 */
patch(Thread.prototype, {
    /**
     * Override the message rendering to properly handle HTML content
     */
    _renderMessage(message) {
        const $message = super._renderMessage(message);
        
        // Find the message body and render HTML content if it contains HTML tags
        const $body = $message.querySelector('.o_mail_thread_message_body');
        if ($body && message.body) {
            const bodyText = message.body;
            if (bodyText && typeof bodyText === 'string' && 
                (bodyText.indexOf('<') !== -1 && bodyText.indexOf('>') !== -1)) {
                
                // This looks like HTML content, render it properly
                const htmlContent = this._sanitizeAndRenderHTML(bodyText);
                $body.innerHTML = htmlContent;
            }
        }
        
        return $message;
    },
    
    /**
     * Sanitize and render HTML content safely
     */
    _sanitizeAndRenderHTML(htmlString) {
        if (!htmlString) {
            return '';
        }
        
        // Create a temporary div to parse and sanitize HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlString;
        
        // Remove any potentially dangerous scripts
        const scripts = tempDiv.querySelectorAll('script');
        scripts.forEach(function(script) {
            script.remove();
        });
        
        // Remove any potentially dangerous iframes
        const iframes = tempDiv.querySelectorAll('iframe');
        iframes.forEach(function(iframe) {
            iframe.remove();
        });
        
        // Remove any potentially dangerous objects
        const objects = tempDiv.querySelectorAll('object, embed');
        objects.forEach(function(obj) {
            obj.remove();
        });
        
        // Return the sanitized HTML
        return tempDiv.innerHTML;
    }
});