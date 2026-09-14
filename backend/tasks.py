SCHEMAS = {
'employee:checkin': {'type':'object','required':['checkin_status','reason','manager_notified','evidence'],'properties':{'checkin_status':{'type':'string','enum':['on_leave','remote_today','running_late','forgot_to_checkin','escalate','unknown']},'reason':{'type':'string'},'manager_notified':{'type':'string','enum':['yes','no','unknown']},'evidence':{'type':'string'}},'additionalProperties':False},
'employee:offboard': {'type':'object','required':['handoff_status','equipment_return','tool_access_confirmed','evidence'],'properties':{'handoff_status':{'type':'string','enum':['confirmed','follow_up_needed','unknown']},'equipment_return':{'type':'string'},'tool_access_confirmed':{'type':'string','enum':['yes','no','unknown']},'evidence':{'type':'string'}},'additionalProperties':False},
'customer:renewal': {'type':'object','required':['decision','plan_after_call','reason','evidence'],'properties':{'decision':{'type':'string','enum':['renewed','downgraded','cancelled','undecided','unknown']},'plan_after_call':{'type':'string'},'reason':{'type':'string'},'evidence':{'type':'string'}},'additionalProperties':False},
'customer:plan': {'type':'object','required':['question','answer','follow_up','evidence'],'properties':{'question':{'type':'string'},'answer':{'type':'string'},'follow_up':{'type':'string'},'evidence':{'type':'string'}},'additionalProperties':False},
'customer:issue': {'type':'object','required':['issue','severity','resolution','escalated','evidence'],'properties':{'issue':{'type':'string'},'severity':{'type':'string','enum':['low','medium','high','unknown']},'resolution':{'type':'string'},'escalated':{'type':'string','enum':['yes','no','unknown']},'evidence':{'type':'string'}},'additionalProperties':False},
'customer:feedback': {'type':'object','required':['sentiment','feedback','follow_up','evidence'],'properties':{'sentiment':{'type':'string','enum':['positive','neutral','negative','unknown']},'feedback':{'type':'string'},'follow_up':{'type':'string'},'evidence':{'type':'string'}},'additionalProperties':False},
'license:usage-review': {'type':'object','required':['decision','seats_after_call','monthly_cost_after_call','reason','evidence'],'properties':{'decision':{'type':'string','enum':['renew_as_is','downgrade','cancel','pending_finance','unknown']},'seats_after_call':{'type':'string'},'monthly_cost_after_call':{'type':'string'},'reason':{'type':'string'},'evidence':{'type':'string'}},'additionalProperties':False},
'license:seat-reclaim': {'type':'object','required':['decision','seats_after_call','monthly_cost_after_call','reason','evidence'],'properties':{'decision':{'type':'string','enum':['renew_as_is','downgrade','cancel','pending_finance','unknown']},'seats_after_call':{'type':'string'},'monthly_cost_after_call':{'type':'string'},'reason':{'type':'string'},'evidence':{'type':'string'}},'additionalProperties':False},
}

def build(pillar, act, e, policies):
    policy = policies.get('employee' if pillar == 'employee' else 'customer' if pillar == 'customer' else 'vendor', '')
    key = f'{pillar}:{act}'
    owner = e.get('owner') or e.get('name') or 'the account owner'
    phone_context = e.get('owner_phone') or e.get('phone')
    if key == 'employee:checkin':
        task = f"Call {e['name']} about a missing attendance check-in. Determine whether they are on approved leave, working remotely, running late, forgot to check in, or need escalation. Be supportive, not disciplinary. Company policy: {policy}"
    elif key == 'employee:offboard':
        task = f"Call {e['name']} on their last working day. Confirm equipment return and that access to {', '.join(e.get('assigned_software', e.get('tools', [])))} can be closed. Be respectful. Company policy: {policy}"
    elif key == 'customer:renewal':
        task = f"Call {e['name']} about the upcoming renewal of their {e['plan']} plan. Confirm whether they want to renew, change plan, or cancel. If cancelling, offer exactly one honest downgrade alternative and then respect their decision. Company policy: {policy}"
    elif key == 'customer:plan':
        task = f"Call {e['name']} and answer questions about their current {e['plan']} plan using only company-approved customer and marketing policy. Capture any follow-up needed. Company policy: {policy}"
    elif key == 'customer:issue':
        task = f"Call {e['name']} about their recent issue. Clarify the problem, determine severity, explain only approved next steps, and escalate if needed. Company policy: {policy}"
    elif key == 'customer:feedback':
        task = f"Call {e['name']} for a short customer feedback conversation. Capture sentiment, the main feedback, and any follow-up. Do not pressure the customer. Company policy: {policy}"
    elif key == 'license:usage-review':
        task = f"Call {owner} about the {e['tool']} subscription. It has {e['seats_active']} active seats out of {e['seats_purchased']} purchased at ${e['cost_per_seat']} per seat/month and renews {e['renewal_date']}. Confirm whether to renew as-is, reduce seats, or cancel. Explain the current unused spend. Vendor policy: {policy}"
    else:
        task = f"Call {owner} about reclaiming an unused {e['tool']} seat after an employee offboarding. Current usage is {e['seats_active']} active of {e['seats_purchased']} purchased. Confirm whether the seat can be reclaimed. Vendor policy: {policy}"
    return task, SCHEMAS[key]
