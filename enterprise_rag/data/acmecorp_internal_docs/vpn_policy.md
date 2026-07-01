# AcmeCorp VPN Access Policy

- **Document ID:** ITSEC-POL-004
- **Version:** 3.2
- **Effective date:** 2026-01-15
- **Policy owner:** IT Security (it-security@acmecorp.example)
- **Applies to:** All employees, contractors, and vendors accessing internal systems remotely

## 1. Purpose and scope

This policy defines how AcmeCorp staff request, use, and retain remote access
to the corporate network through the AcmeCorp VPN. It applies to all remote
connections to internal systems, including production environments, the
corporate intranet, and internal development tools.

## 2. Requesting VPN access

1. Submit the **"VPN Access Request"** form in the IT Service Portal
   (ServiceNow → Service Catalog → Network Access).
2. Your direct manager must approve the request in the portal. Requests
   without manager approval are automatically rejected after 5 business days.
3. IT Security provisions approved requests within **2 business days**.
4. Complete multi-factor authentication (MFA) enrollment in Okta Verify
   before first use. VPN sign-in without MFA is blocked.

New employees: VPN access is part of the standard onboarding checklist — see
the *Employee Onboarding Guide* (HR-GDE-001). Do not submit a duplicate
request if your onboarding ticket already includes one.

## 3. Device requirements

VPN connections are permitted only from devices that meet all of the
following:

- AcmeCorp-managed device enrolled in Jamf (macOS) or Intune (Windows).
- Full-disk encryption enabled.
- CrowdStrike EDR agent installed and reporting.
- Operating system security patches no older than **30 days**.

Personal devices are not permitted on the VPN unless enrolled in the BYOD
program and approved by IT Security.

## 4. Usage rules

- VPN sessions expire after **12 hours**; re-authentication with MFA is
  required.
- Split tunneling is disabled by default. Teams that need split tunneling
  for approved workloads must request an exception (Section 6).
- Sharing VPN credentials or MFA devices is prohibited and treated as a
  security incident (see the *Security Incident Response Playbook*,
  ITSEC-PLB-002).
- Access from countries on the AcmeCorp restricted-region list requires
  prior written approval from IT Security.

## 5. Contractor and vendor access

- Contractor VPN accounts require a named AcmeCorp employee sponsor.
- Contractor access expires automatically after **90 days** and must be
  renewed by the sponsor through the same request form.
- Vendor accounts are restricted to the specific network segments listed in
  the vendor's access agreement.

## 6. Exceptions

Exceptions to this policy (split tunneling, BYOD, restricted regions,
extended contractor terms) must be:

1. Submitted to **security-exceptions@acmecorp.example** with a business
   justification.
2. Approved by the CISO or a delegate.
3. Time-boxed to a maximum of **6 months**, after which they must be
   re-requested.

## 7. Revocation

VPN access is revoked automatically on employment termination, after 60 days
of inactivity, or immediately upon a confirmed policy violation. Managers
must notify IT Security of role changes that remove the need for remote
access.

## 8. Contacts and escalation

| Need | Contact |
|---|---|
| Request status, connection problems | IT Service Desk — #it-helpdesk, ext. 4357 |
| Policy questions, exceptions | IT Security — it-security@acmecorp.example |
| Suspected credential compromise | Security on-call via PagerDuty service "sec-ir" (24/7) |
